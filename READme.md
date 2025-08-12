## Quick start

- drag and drop your code snippets text file "in their pure form" in the repository of your choice "depending on what corresponding task you want your training data to match "example : operator_prediction"
- make sure the code snippets textual file name matches the variable "source_file_path" in the .py file of the corresponding repository "example of the file : operator_prediction.py", or just rename your textual file to "sample_snippets.txt"
- set the destination file name to your likening, or keep it as it is
- run the python script to generate the data

## other modifications

- each task requires a different token vocabulary
- each repository contains the corresponding tokenisation .py file "named tinypy_code_tracer_tokenizer.py"
- so when you will train the model just use this .py file for tokenisation.
- another file that requires changes is the eval.py which contains modifications in the "regex" part, when splitting the example into "input" and "output", so that part is different for each task
- you can use that file as well when training and evaluating
- for these modifications I am not quite sure if all necessary modifications are done "in other words not sure there are other things to modify or just these two file", so double checking is required.

## notes regarding specific tasks

#### stepped operator prediction

step operator prediction works as follows :
- from every "pure" snippet, we execute it and freeze at N random steps "the number of steps is set by the "sampling_limit" hyper parameter"
- sampling_limit = 0 means that it freezes at every step
- at a given frozen step, the states of variables are generated at that moment
- for every frozen step, we try masking M possible operators, one at a time (M is set by the "limit" hyperparameter)
- for each masking, we check whether the operator guessing is deterministic based on the variable states generated previously
- every validated masking generates one training snippet
- In a perfect world, sampling_limit*limit examples can be squeezed out of every pure snippets
- But due to many of these examples being non deterministic, this number becomes more like an upper bound than an exact estimation
- **REMEMBER TO SET THE sampling_limit VARIABLE TO A WEAK VALUE FOR DATASETS INCLUDING LOOPS (ex: 3 to 5), TO AVOID GENERATING A TRAINING SET THAT IS ORDERS OF MAGNITUDE BIGGER THAN THE ORIGINAL PURE DATASET, unless done on purpose**
- the function that filters non-deterministic questions is not perfect, it offers 'weak conditions' to remove as much 'bad' snippets as possible.
- the errored_snippets_are_non_deterministic flag is used to whether ignore or not any code snippets that might raise exeuction errors if the masked operator is replaced with an operator other than the original.
- different_step_answers_are_non_deterministic flag is used to whether ignore or not any code snippet whose execution might not end in the same step if the masked operator is replaced with an operator other than the original.


#### stepped input prediction

stepped input prediction works as follows :
- for every pure snippet, we mask one value at the beginning of the code, and based on the variables states at a specified step, the model must guess the hidden value
- the values that can be masked are values that are in variable assignments of the form x = value, x = value op value, x = value op variable, x = variable op value ..etc
- we are only limiting the masking ability to lines at the beginning of the code, the beginning is defined by anything the precedes the first occurence of an if block or a for/while block
- the code is generated in a way that it is always possible to guess the masked value based on the variables states at any given step
- a single pure snippet can generate ideally n*m training snippets
- n is the number of possible maskings of the different values all across the snippet (specified by the hyperparameter : sampling_limit)
- m is the number of possible steps that we can stop at during the exeuction of the code snippet (specified by the hyperparameter : step_limit)
- we said ideal since many code snippet examples are skipped for not having assignements at the beginning for example ..etc
- there has not been any determinism filtering mechanism created so far, simply because we have not found a scenario where non-determinism can occur in such examples
- **REMEMBER TO SET THE step_limit VARIABLE TO A WEAK VALUE FOR DATASETS INCLUDING LOOPS (ex: 3 to 5), TO AVOID GENERATING A TRAINING SET THAT IS ORDERS OF MAGNITUDE BIGGER THAN THE ORIGINAL PURE DATASET, unless done on purpose**

## some extra stats

I tried documentening the different execution times for each dataset generation.

#### operator prediction (arithmetic and operator)

```
estimated generation time : 850 snippets per second, 7 minutes for 375k snippets
```

#### Output prediction

```
estimated generation time : 6,000 snippets per second, 1 minute for 375k snippets
```

#### Line execution counting

```
estimated generation time : 10,000 snippets per second, 35 seconds for 375k snippets
```

#### stepped operator prediction


```
estimated generation time : 500 snippets per second, 12 minutes for 375k snippets**
**extracted 3 sampled steps from each snippet
```

#### stepped input prediction


```
estimated generation time : 800 snippets per second, 7 minutes for 375k snippets**
** sampling_limit = 3, step_limit = 10
```
