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
