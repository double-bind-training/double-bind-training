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
""" Named entity recognition fine-tuning: utilities to work with CoNLL-2003 task. """


import logging
import os
import pandas as pd


logger = logging.getLogger(__name__)

class InputExample(object):
    """A single training/test example for token classification."""

    def __init__(self, texts, labels):
        """Constructs a InputExample.

        Args:
            guid: Unique id for the example.
            texts: list. The texts of the sequence.
            labels: (Optional) list. The labels for each word of the sequence. This should be
            specified for train and dev examples, but not for test examples.
        """
        # self.guid = guid
        self.texts = texts
        self.labels = labels


class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, input_ids, input_mask, segment_ids, label_ids):
        self.input_ids = input_ids
        self.input_mask = input_mask
        self.segment_ids = segment_ids
        self.label_ids = label_ids


def read_examples_from_file(args, data_dir, mode, delimiter="\t"):
    file_path = os.path.join(data_dir, "{}.tsv".format(mode))
    examples = []

    line_data  = pd.read_csv(file_path, sep=delimiter)

    texts = line_data['text'].values
    labels = line_data['category'].values
    headlines  = line_data['headline'].values

    for text_, label_ in zip(texts, labels):
        examples.append(InputExample(text_, label_))

    return examples
def convert_examples_to_features(instances, tokenizer, labels, max_seq_length):
    label_map = {label: i for i, label in enumerate(labels)}

    features = []
    for instance_idx, instance in enumerate(instances):
        tokenization_result = tokenizer.encode_plus(text=instance.texts,
                                                    max_length=max_seq_length, pad_to_max_length=True,
                                                     truncation=True)
        token_ids = tokenization_result["input_ids"]
        try:
            token_type_ids = tokenization_result["token_type_ids"]
        except:
            token_type_ids = None
        attention_masks = tokenization_result["attention_mask"]

        if instance.labels not in label_map:
            continue
        label = label_map[instance.labels]

        if "num_truncated_tokens" in tokenization_result:
            logger.info(f"Removed {tokenization_result['num_truncated_tokens']} tokens from {instance.text} as they "
                         f"were longer than max_seq_length {max_seq_length}.")

        if instance_idx < 3:
            logger.info("Tokenization example")
            logger.info(f"  text: {instance.texts}")
            logger.info(f"  tokens (by input): {tokenizer.tokenize(instance.texts)}")
            logger.info(f"  token_ids: {tokenization_result['input_ids']}")
            # logger.info(f"  token_type_ids: {tokenization_result['token_type_ids']}")
            logger.info(f"  attention mask: {tokenization_result['attention_mask']}")

        features.append(
            InputFeatures(input_ids=token_ids, input_mask=attention_masks, segment_ids=token_type_ids, label_ids=label)
        )

    return features


def get_labels(path):
    if path:
        with open(path, "r") as f:
            labels = f.read().splitlines()
        return labels
    else:
        return ['sports', 'health', 'technology', 'business', 'politics', 'entertainment', 'religion', 'uncategorized']

#if __name__ == "__main__":
#    examples = read_examples_from_file('data/pos_data_100/pcm/', 'test')
#    print(len(examples))