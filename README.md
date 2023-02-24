
# double-bind-training
You'll need to install pipenv or you can use requirement.txt to setup your environment.

> Note: You should rename the project key in `wandb.init()` before you run train_ner_adapter or else it'll save the run the task in same window.

Once you are setup run the following in command line and paste your wandb team api key to setup you wandb env:-

```
wandb login
```

## About the Dataset

Currently we've support for **MAFAND** dataset for language modelling task and **Masakhane-NER** dataset for NER Dataset in the colab notebook. This support is yet to be extended.

Sometimes you might face an issue related to `train.txt` being available that is because some language dataset don't have a training set present!

## Colab Notebooks

At present we have 2 main colab notebooks:-

* [Adapter Train NER complete (AfricaNLP Experiments)](https://colab.research.google.com/drive/1U8UtduIKStS84sEgn3QIzCuOjtwor3_y?usp=sharing): This has the pipeline needed to train Adapters on language modeling and NER Task.
* [BaseLine Train NER  (AfricaNLP Experiments)](https://colab.research.google.com/drive/1RmRjQe1pJlR1WqXpcNIRYL33hKdk6wQT?usp=sharing): This has the pipeline needed to fine-tune Baseline models on NER Task.

## Adapter Training Part 1 - Language Modeling

First task is to train Adapters for Language modelling for which the code can be found under `train_lm_adapter.py` this script is triggered in 1st colab notebook after parameters are set in the initial cells. An example call is shown below:-

```
!CUDA_VISIBLE_DEVICES=0,1 python train_lm_adapter.py \
--model_name_or_path "xlmroberta-base" \
--train_file train.txt \
--validation_file validation.txt \
--per_device_train_batch_size 8 \
--per_device_eval_batch_size 8 \
--train_adapter \
--do_train \
--seed 42 \
--do_eval \
--overwrite_output_dir \
--num_train_epochs 20 \
--report_to "wandb" \
--run_name "adapter-training-lm-test" \
--output_dir /tmp/test-mlm \
--tags "hau,xlmroberta-base" \
--logging_steps 99
```
List of parameters that can be modified is mentioned below:-
| Parameter | Description |
|--|--|
| `model_name_or_path` |  |
| `train_file` |  |
| `validation_file` |  |
| `per_device_train_batch_size` |  |
| `per_device_eval_batch_size` |  |
| `train_adapter` |  |
| `do_train` |  |
| `do_eval` |  |
| `seed` |  |
| `overwrite_output_dir` |  |
| `num_train_epochs` |  |
| `report_to` |  |
| `run_name` |  |
| `output_dir` |  |
| `tags` |  |
| `logging_steps` |  |
| `gradient_accumulation_steps` |  |
| `save_steps` |  |
| `push_to_hub` |  |
| `push_to_hub_model_id` |  |
| `push_to_hub_organization` |  |
| `push_to_hub_token` |  |

## Adapter Training Part 2 - NER

Second task is to fine-tune Adapter trained for Language modelling above on NER task for which the code can be found under `train_ner_adapter.py` this script is triggered in 1st colab notebook after parameters are set in the initial cells. An example call is shown below:-

```
!CUDA_VISIBLE_DEVICES=0,1 python3 train_ner_adapter.py --data_dir data/"$language_code" \
--model_type roberta \
--model_name_or_path "$ADAPTER_MODEL" \
--output_dir "$OUTPUT_DIR" \
--max_seq_length "$MAX_LENGTH" \
--num_train_epochs "$NUM_EPOCHS" \
--per_gpu_train_batch_size "$BATCH_SIZE" \
--save_steps $SAVE_STEPS --learning_rate 5e-4 \
--seed $SEED \
--tags "$language_code,$lm_adapter_training_model_name_or_path,$LM_WANDB_RUN_NAME" \
--path_to_adapter /tmp/test-mlm \
--overwrite_output_dir \
--do_train \
--do_eval \
--do_predict
```
List of parameters that can be modified is mentioned below:-
| Parameter | Description |
|--|--|
| `data_dir` |  |
| `model_type` |  |
| `model_name_or_path` |  |
| `max_seq_length` |  |
| `per_gpu_train_batch_size` |  |
| `save_steps` |  |
| `learning_rate` |  |
| `tags` |  |
| `seed` |  |
| `path_to_adapter` |  |
| `overwrite_output_dir` |  |
| `do_train` |  |
| `do_eval` |  |
| `do_predict` |  |