
<!---
Copyright 2020 The HuggingFace Team. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Contribute to Code

Everyone is welcome to contribute, and we value everybody's contribution. Code contributions are not the only way to help the community. Answering questions, helping others, and improving the documentation are also immensely valuable.

**This guide was heavily inspired by the awesome [transformers guide to contributing](https://github.com/huggingface/transformers/blob/main/CONTRIBUTING.md).**

## Ways to contribute

There are several ways you can contribute:

* Fix outstanding issues with the existing code.
* Submit issues related to bugs or desired new features

Just comment in the issue that you'd like to work on it, someone in the team will confirm and you'll be added as contributor for the task. 

## Fixing outstanding issues

If you notice an issue with the existing code and have a fix in mind, feel free to [start contributing](https://github.com/huggingface/transformers/blob/main/CONTRIBUTING.md/#create-a-pull-request) and open a Pull Request!

## Submitting a bug-related issue or feature request

Do your best to follow these guidelines when submitting a bug-related issue or a feature request. It will make it easier for us to come back to you quickly and with good feedback.

### Did you find a bug?

Before you report an issue, we would really appreciate it if you could **make sure the bug was not already reported** (use the search bar on GitHub under Issues). Your issue should also be related to bugs in the library itself, and not your code. If you're unsure whether the bug is in your code or the library, please ask on the slack channel first. This helps us respond quicker to fixing issues related to the library versus general questions.

Once you've confirmed the bug hasn't already been reported, please include the following information in your issue so we can quickly resolve it:

* A short, self-contained, code snippet that allows us to reproduce the bug in less than 30s.
* The *full* traceback if an exception is raised.
* Attach any other additional information, like screenshots, you think may help.

### Do you want a new feature?

If there is a new feature you'd like to see, please open an issue and describe it. If your issue is well written we're already 80% of the way there by the time you create it.

## Create a Pull Request

Before writing any code, we strongly advise you to search through the existing PRs or issues to make sure nobody is already working on the same thing. If you are unsure, it is always a good idea to open an issue to get some feedback. You will need basic `git` proficiency to contribute. 

While `git` is not the easiest tool to use, it has the greatest manual. Type `git --help` in a shell and enjoy! If you prefer books, [Pro Git](https://git-scm.com/book/en/v2) is a very good reference. You'll need Python 3.10 to contribute. Follow the steps below to start contributing:

1. Fork the repository by clicking on the **Fork** button on the repository's page. This creates a copy of the code under your GitHub user account.

2. Clone your fork to your local disk, and add the base repository as a remote:

   ```bash
   $ git clone git@github.com:<your Github handle>/double-bind-training.git
   $ cd double-bind-training
   $ git remote add upstream https://github.com/double-bind-training/double-bind-training.git
   ```

3. Create a new branch to hold your development changes:

   ```bash
   $ git checkout -b a-descriptive-name-for-my-changes
   ```

   🚨 **Do not** work on the `main` branch!

4. Set up a development environment by running the following command in a virtual environment:

   ```bash
   $ pipenv install
   $ pipenv shell
   ```

5. Now you can go to your fork of the repository on GitHub and click on **Pull request** to open a pull request. When you're ready, you can send your changes to the project maintainers for review.

6. It's ok if maintainers request changes, it happens to our core contributors too! So everyone can see the changes in the pull request, work in your local branch and push the changes to your fork. They will automatically appear in the pull request.