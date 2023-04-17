# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Fine-tuning the library models for named entity recognition on CoNLL-2003 (Bert or Roberta). """

import argparse
import glob
import logging
import os
import random

import numpy as np
import pandas as pd
import torch
from seqeval.metrics import f1_score, precision_score, recall_score, classification_report
from torch.nn import CrossEntropyLoss
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler, TensorDataset
from torch.utils.data.distributed import DistributedSampler
from tqdm import tqdm, trange
from torch.utils.data import TensorDataset

from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from torch import LongTensor
import torch
from torch import nn
from tqdm import tqdm
import random


from transformers import (
    WEIGHTS_NAME,
    AdamW,
    AutoConfig,
    AutoTokenizer,
    XLMRobertaTokenizer,
    AutoAdapterModel,
    get_linear_schedule_with_warmup,
)

import wandb
from utils_news import convert_examples_to_features, get_labels, read_examples_from_file
from torch.utils.data import DataLoader
import sklearn.metrics

logger = logging.getLogger(__name__)

MODEL_CLASSES = {
    "bert": "",
    "roberta": "",
    "distilbert": "",
    "camembert": "",
    "xlmroberta": "",
}
try:
    from torch.utils.tensorboard import SummaryWriter
except ImportError:
    from tensorboardX import SummaryWriter

def set_seed(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.n_gpu > 0:
        torch.cuda.manual_seed_all(args.seed)

def train(args, train_dataset, dev_dataset, labels, model, tokenizer,  adapter_name):
    model.train_adapter(adapter_name)
    """ Train the model """
    if args.local_rank in [-1, 0]:
      tb_writer = SummaryWriter()
    # loss_fct = torch.nn.CrossEntropyLoss()
    args.train_batch_size = args.per_gpu_train_batch_size * max(1, args.n_gpu)
    train_sampler = RandomSampler(train_dataset) if args.local_rank == -1 else DistributedSampler(train_dataset)
    train_dataloader = DataLoader(train_dataset, sampler=train_sampler, batch_size=args.train_batch_size)

    if args.max_steps > 0:
        t_total = args.max_steps
        args.num_train_epochs = args.max_steps // (len(train_dataloader) // args.gradient_accumulation_steps) + 1
    else:
        t_total = len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs

    # Prepare optimizer and schedule (linear warmup and decay)
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {
            "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
            "weight_decay": args.weight_decay,
        },
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=args.warmup_steps, num_training_steps=t_total
    )

    # Check if saved optimizer or scheduler states exist
    '''
    if os.path.isfile(os.path.join(args.model_name_or_path, "optimizer__.pt")) and os.path.isfile(
        os.path.join(args.model_name_or_path, "scheduler__.pt")
    ):
        # Load in optimizer and scheduler states
        optimizer.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "optimizer.pt")))
        scheduler.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "scheduler.pt")))
    '''

    # multi-gpu training (should be after apex fp16 initialization)
    if args.n_gpu > 1:
        model = torch.nn.DataParallel(model)

    # Distributed training (should be after apex fp16 initialization)
    if args.local_rank != -1:
        model = torch.nn.parallel.DistributedDataParallel(
            model, device_ids=[args.local_rank], output_device=args.local_rank, find_unused_parameters=True
        )

    # Train!
    logger.info("***** Running training *****")
    logger.info("  Num examples = %d", len(train_dataset))
    logger.info("  Num Epochs = %d", args.num_train_epochs)
    logger.info("  Instantaneous batch size per GPU = %d", args.per_gpu_train_batch_size)
    logger.info(
        "  Total train batch size (w. parallel, distributed & accumulation) = %d",
        args.train_batch_size
        * args.gradient_accumulation_steps
        * (torch.distributed.get_world_size() if args.local_rank != -1 else 1),
    )
    logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)
    logger.info("  Total optimization steps = %d", t_total)

    global_step = 0
    epochs_trained = 0
    steps_trained_in_current_epoch = 0
    # Check if continuing training from a checkpoint
    '''
    if os.path.exists(args.output_dir): #model_name_or_path):
        # set global_step to gobal_step of last saved checkpoint from model path
        global_step = int(args.model_name_or_path.split("-")[-1].split("/")[0])
        epochs_trained = global_step // (len(train_dataloader) // args.gradient_accumulation_steps)
        steps_trained_in_current_epoch = global_step % (len(train_dataloader) // args.gradient_accumulation_steps)
        logger.info("  Continuing training from checkpoint, will skip to saved global_step")
        logger.info("  Continuing training from epoch %d", epochs_trained)
        logger.info("  Continuing training from global step %d", global_step)
        logger.info("  Will skip the first %d steps in the first epoch", steps_trained_in_current_epoch)
    '''
    tr_loss, logging_loss = 0.0, 0.0
    model.zero_grad()
    train_iterator = trange(
        epochs_trained, int(args.num_train_epochs), desc="Epoch", disable=args.local_rank not in [-1, 0]
    )
    set_seed(args)  # Added here for reproductibility

    eval_fones = []
    for _ in train_iterator:
        epoch_iterator = tqdm(train_dataloader, desc="Iteration", disable=args.local_rank not in [-1, 0])
        for step, batch in enumerate(epoch_iterator):
            # Skip past any already trained steps if resuming training
            if steps_trained_in_current_epoch > 0:
                steps_trained_in_current_epoch -= 1
                continue

            model.train()
            batch = tuple(t.to(args.device) for t in batch)
            inputs = {"input_ids": batch[0], "attention_mask": batch[1], "labels": batch[-1]}
            if args.model_type not in ["distilbert", "xlmroberta"]:
                inputs["token_type_ids"] = (
                    batch[2] if args.model_type in ["bert"] else None
                )  # XLM and DistilBERT don't use segment_ids
            outputs = model(**inputs)
            loss = outputs[0]  # model outputs are always tuple in transformers (see doc)

            if args.n_gpu > 1:
                loss = loss.mean()  # mean() to average on multi-gpu parallel training
            if args.gradient_accumulation_steps > 1:
                loss = loss / args.gradient_accumulation_steps

            loss.backward()

            tr_loss += loss.item()
            if (step + 1) % args.gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)

                optimizer.step()
                scheduler.step()  # Update learning rate schedule
                model.zero_grad()
                global_step += 1


            if args.max_steps > 0 and global_step > args.max_steps:
                epoch_iterator.close()
                break

        # EVALUATE + EARLY STOPPING
        if global_step > 500 and args.n_gpu == 1: # and global_step % args.save_steps == 0:
            eval_results, _ = evaluate(args, model, tokenizer, labels, "dev", display_res=True)
            f1_step = round(eval_results["eval_acc"], 5)
            eval_fones.append(f1_step)
            print("eval result: ", global_step, f1_step)

            #n = 1
            #while len(eval_fones) > 5 and n < 6 and eval_fones[-1] < eval_fones[-1 * (n + 1)]:
            #    print("no: ", n)
            #    n += 1

            #if n == 6:
            #    logger.info("EARLY STOPPING ..... ")
            #    break

            max_f1 = max(eval_fones)

            if f1_step == max_f1:
                output_dir = args.output_dir
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                model_to_save = (
                    model.module if hasattr(model, "module") else model
                )  # Take care of distributed/parallel training
                model_to_save.save_pretrained(output_dir)
                tokenizer.save_pretrained(output_dir)

                torch.save(args, os.path.join(output_dir, "training_args.bin"))
                logger.info("Saving model checkpoint to %s", output_dir)

                #torch.save(optimizer.state_dict(), os.path.join(output_dir, "optimizer.pt"))
                #torch.save(scheduler.state_dict(), os.path.join(output_dir, "scheduler.pt"))
                #logger.info("Saving optimizer and scheduler states to %s", output_dir)


        if args.max_steps > 0 and global_step > args.max_steps:
            train_iterator.close()
            break

    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    model_to_save = (
        model.module if hasattr(model, "module") else model
    )  # Take care of distributed/parallel training
    model_to_save.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    torch.save(args, os.path.join(output_dir, "training_args.bin"))
    logger.info("Saving model checkpoint to %s", output_dir)

    if args.local_rank in [-1, 0]:
        tb_writer.close()


    for i in os.listdir(args.output_dir):
        wandb.save(f"{args.output_dir}/{i}")

    return global_step, tr_loss / global_step


def evaluate(args, model, tokenizer, labels, mode, prefix="", display_res=False):
    eval_dataset = load_and_cache_examples(args, tokenizer, labels, mode)
    
    args.eval_batch_size = args.per_gpu_eval_batch_size * max(1, args.n_gpu)
    # Note that DistributedSampler samples randomly
    eval_sampler = SequentialSampler(eval_dataset)
    eval_dataloader = DataLoader(eval_dataset, sampler=eval_sampler, batch_size=args.eval_batch_size)

    # multi-gpu eval
    #if args.n_gpu > 1:
    #    model = torch.nn.DataParallel(model)

    # Eval!
    logger.info("***** Running evaluation {} *****".format(prefix))
    logger.info("  Num examples = %d", len(eval_dataset))
    logger.info("  Batch size = %d", args.eval_batch_size)
    eval_loss = 0.0
    nb_eval_steps = 0
    preds = None
    out_label_ids = None
    for batch in tqdm(eval_dataloader, desc="Evaluating"):
        model.eval()
        batch = tuple(t.to(args.device) for t in batch)

        with torch.no_grad():
            inputs = {"input_ids": batch[0], "attention_mask": batch[1], "labels": batch[-1]}
            if args.model_type != "distilbert":
                inputs["token_type_ids"] = (
                    batch[2] if args.model_type in ["bert"] else None
                )  # XLM and DistilBERT don't use segment_ids
            outputs = model(**inputs)
            tmp_eval_loss, logits = outputs[:2]

            eval_loss += tmp_eval_loss.mean().item()
        nb_eval_steps += 1
        if preds is None:
            preds = logits.detach().cpu().numpy()
            out_label_ids = inputs["labels"].detach().cpu().numpy()
        else:
            preds = np.append(preds, logits.detach().cpu().numpy(), axis=0)
            out_label_ids = np.append(out_label_ids, inputs["labels"].detach().cpu().numpy(), axis=0)

    eval_loss = eval_loss / nb_eval_steps
    preds = np.argmax(preds, axis=1)
    eval_report = sklearn.metrics.classification_report(out_label_ids, preds,
                                                        labels=range(len(labels)),
                                                        target_names=labels,
                                                        output_dict=True
                                                        )

    # results = {
    #     "loss": eval_loss,
    #     "precision": eval_report["weighted avg"]["precision"],
    #     "recall": eval_report["weighted avg"]["recall"],
    #     "acc": sklearn.metrics.accuracy_score(out_label_ids, preds),
    #     "f1": eval_report["weighted avg"]["f1-score"]
    # }

    
  #  results = {
  #       "loss": eval_loss,
  #       "precision": eval_report["weighted avg"]["precision"],
  #       "recall": eval_report["weighted avg"]["recall"],
  #       "acc": sklearn.metrics.accuracy_score(out_label_ids, preds),
  #       "f1": eval_report["weighted avg"]["f1-score"]
  #   }
    results = {}
    if mode=="dev":
        results = {
            "eval_loss": eval_loss,
            "eval_precision": eval_report["weighted avg"]["precision"],
            "eval_recall": eval_report["weighted avg"]["recall"],
            "eval_acc": sklearn.metrics.accuracy_score(out_label_ids, preds),
            'eval_f1': eval_report["weighted avg"]["f1-score"],
        }
    
    elif mode=="test":
        results = {
            "predict_loss": eval_loss,
            "predict_precision": eval_report["weighted avg"]["precision"],
            "predict_recall": eval_report["weighted avg"]["recall"],
            "predict_acc": sklearn.metrics.accuracy_score(out_label_ids, preds),
            'predict_f1': eval_report["weighted avg"]["f1-score"],
        }
    if not display_res:
        logger.info("***** Eval results {} *****".format(prefix))
        for key in sorted(results.keys()):
            logger.info("  %s = %s", key, str(results[key]))
            
    wandb.log(results)

    print(f"***** Eval results {prefix} *****")
    for key in sorted(results.keys()):
        print(f"{key} = {str(results[key])}")

    return results, preds

def load_and_cache_examples(args, tokenizer, labels, mode):
    if args.local_rank not in [-1, 0] and not evaluate:
        torch.distributed.barrier()  # Make sure only the first process in distributed training process the dataset, and the others will use the cache

    # Load data features from cache or dataset file
    cached_features_file = os.path.join(
        args.data_dir,
        "cached_{}_{}_{}".format(
            mode, list(filter(None, args.model_name_or_path.split("/"))).pop(), str(args.max_seq_length)
        ),
    )
    if os.path.exists(cached_features_file) and not args.overwrite_cache:
        print("Loading features from cached file", cached_features_file)
        features = torch.load(cached_features_file)
    else:
        print("Creating features from dataset file at", args.data_dir)
      #  logger.info("Creating features from dataset file at %s", args.data_dir)
        instances = read_examples_from_file(args, args.data_dir, mode)
        features = convert_examples_to_features(instances, tokenizer, labels, args.max_seq_length)
        if args.local_rank in [-1, 0]:
            logger.info("Saving features into cached file %s", cached_features_file)
            torch.save(features, cached_features_file)
        # print("Creating features from dataset file at", args.data_dir)
        # examples = read_examples_from_file(args,args.data_dir, mode)
        # features = convert_examples_to_features(
        #     examples,
        #     labels,
        #     args.max_seq_length,
        #     tokenizer,
        #     cls_token_at_end=bool(args.model_type in ["xlnet"]),
        #     # xlnet has a cls token at the end
        #     cls_token=tokenizer.cls_token,
        #     cls_token_segment_id=2 if args.model_type in ["xlnet"] else 0,
        #     sep_token=tokenizer.sep_token,
        #     sep_token_extra=bool(args.model_type in ["roberta"]),
        #     # roberta uses an extra separator b/w pairs of sentences, cf. github.com/pytorch/fairseq/commit/1684e166e3da03f5b600dbb7855cb98ddfcd0805
        #     pad_on_left=bool(args.model_type in ["xlnet"]),
        #     # pad on the left for xlnet
        #     pad_token=tokenizer.convert_tokens_to_ids([tokenizer.pad_token])[0],
        #     pad_token_segment_id=4 if args.model_type in ["xlnet"] else 0,
        #     pad_token_label_id=pad_token_label_id,
        # )
        if args.local_rank in [-1, 0]:
            print("Saving features into cached file", cached_features_file)
            torch.save(features, cached_features_file)

    if args.local_rank == 0 and not evaluate:
        torch.distributed.barrier()  # Make sure only the first process in distributed training process the dataset, and the others will use the cache
    # Convert to Tensors and build dataset
    all_input_ids = torch.tensor([f.input_ids for f in features], dtype=torch.long)
    all_input_mask = torch.tensor([f.input_mask for f in features], dtype=torch.long)
    all_label_ids = torch.tensor([f.label_ids for f in features], dtype=torch.long)

    dataset = TensorDataset(all_input_ids, all_input_mask, all_label_ids)
    return dataset



def main():
    parser = argparse.ArgumentParser()

    # Required parameters
    parser.add_argument(
        "--data_dir",
        default=None,
        type=str,
        required=True,
        help="The input data dir. Should contain the training files for the CoNLL-2003 NER task.",
    )
    parser.add_argument(
        "--model_type",
        default=None,
        type=str,
        required=True,
        help="Model type selected in the list: " + ", ".join(MODEL_CLASSES.keys()),
    )
    parser.add_argument(
        "--model_name_or_path",
        default=None,
        type=str,
        required=True,
        help="Path to pre-trained model or shortcut name selected in the list: " + ", ",
    )
    parser.add_argument(
        "--input_dir",
        default=None,
        type=str,
        required=False,
        help="The input model directory.",
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        type=str,
        required=True,
        help="The output directory where the model predictions and checkpoints will be written.",
    )
    parser.add_argument(
        "--test_result_file",
        default="test_results.txt",
        type=str,
        required=False,
        help="The test_result",
    )

    parser.add_argument(
        "--test_prediction_file",
        default="test_predictions.txt",
        type=str,
        required=False,
        help="The test_result",
    )
    parser.add_argument(
        "--output_result",
        default=None,
        type=str,
        help="The file the  output evaluation result.",
    )
    # Other parameters
    parser.add_argument(
        "--labels",
        default="",
        type=str,
        help="Path to a file containing all labels. If not specified, CoNLL-2003 labels are used.",
    )
    
    parser.add_argument(
        "--config_name", default="", type=str, help="Pretrained config name or path if not the same as model_name"
    )
    parser.add_argument(
        "--tokenizer_name",
        default="",
        type=str,
        help="Pretrained tokenizer name or path if not the same as model_name",
    )
    parser.add_argument(
        "--cache_dir",
        default="",
        type=str,
        help="Where do you want to store the pre-trained models downloaded from s3",
    )
    parser.add_argument(
        "--max_seq_length",
        default=128,
        type=int,
        help="The maximum total input sequence length after tokenization. Sequences longer "
        "than this will be truncated, sequences shorter will be padded.",
    )
    parser.add_argument("--do_train", action="store_true", help="Whether to run training.")
    parser.add_argument("--do_finetune", action="store_true", help="Whether to run training.")
    parser.add_argument("--do_eval", action="store_true", help="Whether to run eval on the dev set.")
    parser.add_argument("--do_predict", action="store_true", help="Whether to run predictions on the test set.")
    parser.add_argument(
        "--evaluate_during_training",
        action="store_true",
        help="Whether to run evaluation during training at each logging step.",
    )
    parser.add_argument(
        "--do_lower_case", action="store_true", help="Set this flag if you are using an uncased model."
    )

    parser.add_argument("--per_gpu_train_batch_size", default=8, type=int, help="Batch size per GPU/CPU for training.")
    parser.add_argument(
        "--per_gpu_eval_batch_size", default=8, type=int, help="Batch size per GPU/CPU for evaluation."
    )
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=1,
        help="Number of updates steps to accumulate before performing a backward/update pass.",
    )
    parser.add_argument("--learning_rate", default=5e-5, type=float, help="The initial learning rate for Adam.")
    parser.add_argument("--weight_decay", default=0.0, type=float, help="Weight decay if we apply some.")
    parser.add_argument("--adam_epsilon", default=1e-8, type=float, help="Epsilon for Adam optimizer.")
    parser.add_argument("--max_grad_norm", default=1.0, type=float, help="Max gradient norm.")
    parser.add_argument(
        "--num_train_epochs", default=3.0, type=float, help="Total number of training epochs to perform."
    )
    parser.add_argument(
        "--max_steps",
        default=-1,
        type=int,
        help="If > 0: set total number of training steps to perform. Override num_train_epochs.",
    )
    parser.add_argument("--warmup_steps", default=0, type=int, help="Linear warmup over warmup_steps.")

    parser.add_argument("--logging_steps", type=int, default=500, help="Log every X updates steps.")
    parser.add_argument("--save_steps", type=int, default=500, help="Save checkpoint every X updates steps.")
    parser.add_argument(
        "--eval_all_checkpoints",
        action="store_true",
        help="Evaluate all checkpoints starting with the same prefix as model_name ending and ending with step number",
    )
    parser.add_argument("--no_cuda", action="store_true", help="Avoid using CUDA when available")
    parser.add_argument(
        "--overwrite_output_dir", action="store_true", help="Overwrite the content of the output directory"
    )
    parser.add_argument(
        "--overwrite_cache", action="store_true", help="Overwrite the cached training and evaluation sets"
    )
    parser.add_argument("--seed", type=int, default=42, help="random seed for initialization")

    parser.add_argument("--local_rank", type=int, default=-1, help="For distributed training: local_rank")
    parser.add_argument("--server_ip", type=str, default="", help="For distant debugging.")
    parser.add_argument("--server_port", type=str, default="", help="For distant debugging.")
    parser.add_argument("--tags", type=str, default="", help="Set the tag for wandb project run.")
    parser.add_argument("--path_to_adapter", type=str, help="Directory containing path to adapter.")

    args = parser.parse_args()
    
    wandb.init(project="masakhane-news-test-run", entity="double-bind-ner", tags=args.tags.split(','), config = {
        "max length": os.getenv('MAX_LENGTH'),
        "adapter model": os.getenv('ADAPTER_MODEL'),
        "output dir": os.getenv('OUTPUT_DIR'),
        "batch size": os.getenv('BATCH_SIZE'),
        "epochs": os.getenv('NUM_EPOCHS'),
        "save steps": os.getenv('SAVE_STEPS'),
        "seed": os.getenv('SEED'),
    })

    if (
        os.path.exists(args.output_dir)
        and os.listdir(args.output_dir)
        and args.do_train
        and not args.overwrite_output_dir
    ):
        raise ValueError(
            "Output directory ({}) already exists and is not empty. Use --overwrite_output_dir to overcome.".format(
                args.output_dir
            )
        )

    # Setup distant debugging if needed
    if args.server_ip and args.server_port:
        # Distant debugging - see https://code.visualstudio.com/docs/python/debugging#_attach-to-a-local-script
        import ptvsd

        print("Waiting for debugger attach")
        ptvsd.enable_attach(address=(args.server_ip, args.server_port), redirect_output=True)
        ptvsd.wait_for_attach()

    # Setup CUDA, GPU & distributed training
    if args.local_rank == -1 or args.no_cuda:
        device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
        args.n_gpu = torch.cuda.device_count()
    else:  # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
        torch.cuda.set_device(args.local_rank)
        device = torch.device("cuda", args.local_rank)
        torch.distributed.init_process_group(backend="nccl")
        args.n_gpu = 1
    args.device = device

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO if args.local_rank in [-1, 0] else logging.WARN,
    )

    # Set seed
    set_seed(args)

    # Prepare CONLL-2003 task
    labels = get_labels(args.labels)
    num_labels = len(labels)
    args.num_labels = num_labels

    print(labels)
    # Use cross entropy ignore index as padding label id so that only real label ids contribute to the loss later
    pad_token_label_id = CrossEntropyLoss().ignore_index

    # Load pretrained model and tokenizer
    if args.local_rank not in [-1, 0]:
        torch.distributed.barrier()  # Make sure only the first process in distributed training will download model & vocab
    args.model_type = args.model_type.lower()
    if args.model_name_or_path=='bonadossou/afrolm_active_learning':
        config_class, model_class, tokenizer_class = AutoConfig, AutoAdapterModel, XLMRobertaTokenizer #MODEL_CLASSES[args.model_type]
    else:
        config_class, model_class, tokenizer_class = AutoConfig, AutoAdapterModel, AutoTokenizer #MODEL_CLASSES[args.model_type]
    model = model_class.from_pretrained(args.model_name_or_path)
    
    adapter_name = model.load_adapter(args.path_to_adapter)
    model.set_active_adapters(adapter_name)

    model.add_classification_head("news_head", num_labels=len(labels))
    print(model)

    tokenizer = tokenizer_class.from_pretrained(
        args.tokenizer_name if args.tokenizer_name else args.model_name_or_path,
        # do_lower_case=args.do_lower_case,
        cache_dir=args.cache_dir if args.cache_dir else None,
        # use_fast=args.use_fast,
    )

    if args.local_rank == 0:
        torch.distributed.barrier()  # Make sure only the first process in distributed training will download model & vocab

    model.to(args.device)
    print("Training/evaluation parameters", args)

    # Training
    if args.do_train:
        # train_dataset = load_and_cache_examples(args, tokenizer, labels, pad_token_label_id, mode="train")
        #train_dataset = load_examples(args, mode="train")
        # global_step, tr_loss = train(args, train_dataset, model, tokenizer, labels, pad_token_label_id, adapter_name)
        #global_step, tr_loss = train_ner(args, train_dataset, model, tokenizer, labels, pad_token_label_id)
        train_dataset = load_and_cache_examples(args, tokenizer, labels, mode="train")
        dev_dataset = load_and_cache_examples(args, tokenizer, labels, mode="dev")
        global_step, tr_loss = train(args, train_dataset, dev_dataset, labels, model, tokenizer,adapter_name)
        logger.info(" global_step = %s, average loss = %s", global_step, tr_loss)

        print(f" global_step = {global_step}, average loss = {tr_loss}")

    # Fine-tuning
    if args.do_finetune:
        tokenizer = tokenizer_class.from_pretrained(args.input_dir, do_lower_case=args.do_lower_case)
        model = model_class.from_pretrained(args.input_dir)
        model.to(args.device)
        result, predictions = evaluate(args, model, tokenizer, labels, pad_token_label_id, mode="test")
        train_dataset = load_and_cache_examples(args, tokenizer, labels, pad_token_label_id, mode="train")

        # train_dataset = load_examples(args, mode="train")
        global_step, tr_loss = train(args, train_dataset, model, tokenizer, labels, pad_token_label_id)
        # global_step, tr_loss = train_ner(args, train_dataset, model, tokenizer, labels, pad_token_label_id)
        print(f" global_step = {global_step}, average loss = {tr_loss}")

    # Saving best-practices: if you use defaults names for the model, you can reload it using from_pretrained()
    if args.do_train and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
        # Create output directory if needed
        if not os.path.exists(args.output_dir) and args.local_rank in [-1, 0]:
            os.makedirs(args.output_dir)

        print("Saving model checkpoint to", args.output_dir)
        # Save a trained model, configuration and tokenizer using `save_pretrained()`.
        # They can then be reloaded using `from_pretrained()`

        model_to_save = (
            model.module if hasattr(model, "module") else model
        )  # Take care of distributed/parallel training

        tokenizer.save_pretrained(args.output_dir)
        model_to_save.save_pretrained(args.output_dir)

        # Good practice: save your training arguments together with the trained model
        torch.save(args, os.path.join(args.output_dir, "training_args.bin"))
    
    # Evaluation
    results = {}
    if args.do_eval and args.local_rank in [-1, 0]:
        tokenizer = tokenizer_class.from_pretrained(args.output_dir, do_lower_case=args.do_lower_case)
        checkpoints = [args.output_dir]
        if args.eval_all_checkpoints:
            checkpoints = list(
                os.path.dirname(c) for c in sorted(glob.glob(args.output_dir + "/**/" + WEIGHTS_NAME, recursive=True))
            )
            logging.getLogger("pytorch_transformers.modeling_utils").setLevel(logging.WARN)  # Reduce logging
        print("Evaluate the following checkpoints: ", checkpoints)
        for checkpoint in checkpoints:
            global_step = checkpoint.split("-")[-1] if len(checkpoints) > 1 else ""
            prefix = checkpoint.split("/")[-1] if checkpoint.find("checkpoint") != -1 else ""

            #model = model_class.from_pretrained(checkpoint)
            #model.to(args.device)
            result, _ = evaluate(args, model, tokenizer, labels, mode='dev', prefix=prefix)
            result = dict((k + "_{}".format(global_step), v) for k, v in result.items())
            results.update(result)

    if args.do_predict and args.local_rank in [-1, 0]:
        tokenizer = tokenizer_class.from_pretrained(args.output_dir, do_lower_case=args.do_lower_case)
        # model = model_class.from_pretrained(args.output_dir)
        # model.to(args.device)
        result, predictions = evaluate(args, model, tokenizer, labels, mode='test')
        predictions = list(predictions)
        id2label = {str(i): label for i, label in enumerate(labels)}

        # Save results
        output_test_results_file = os.path.join(args.output_dir,"result.txt")
        with open(output_test_results_file, "w") as writer:
            for key in sorted(result.keys()):
                writer.write("{} = {}\n".format(key, str(result[key])))

        output_test_predictions_file = os.path.join(args.output_dir, "prediction_result.txt")
        with open(output_test_predictions_file, "w", encoding='utf-8') as writer:
            test_path = os.path.join(args.data_dir, "test.tsv")
            test_set = pd.read_csv(test_path, delimiter = "\t")
            
            texts = test_set['text'].values
            labels = test_set['category'].values
            headlines  = test_set['headline'].values

            for idx, (text_, headline_, label_) in enumerate(zip(texts, headlines, labels)):
                text_ = headline_.strip() + ". " + text_.strip()
                output_line = text_ + "\t" + id2label[str(predictions[idx])] + "\n"
                writer.write(output_line)

    wandb.finish(exit_code=0)
    return results

if __name__ == "__main__":
    main()

'''
export MAX_LENGTH=164
export ADAPTER_MODEL=xlm-roberta-base
export OUTPUT_DIR=yo_sample
export BATCH_SIZE=32
export NUM_EPOCHS=50
export SAVE_STEPS=10000
export SEED=1

CUDA_VISIBLE_DEVICES=1 python3 train_pos_adapter.py --data_dir conll_format/yoruba/ \
--model_type bert \
--model_name_or_path $ADAPTER_MODEL \
--output_dir $OUTPUT_DIR \
--max_seq_length  $MAX_LENGTH \
--num_train_epochs $NUM_EPOCHS \
--per_gpu_train_batch_size $BATCH_SIZE \
--save_steps $SAVE_STEPS --learning_rate 5e-4 \
--seed $SEED \
--do_train \
--do_eval \
--do_predict
'''
