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
- every validated masking generates one training snippet ( that can be non-deterministic)
- In a perfect world, sampling_limit*limit examples can be squeezed out of every pure snippets
- But due to many of these examples not having operators to replace "only assignements for example", this number becomes more like an upper bound than an exact estimation
- **REMEMBER TO SET THE sampling_limit VARIABLE TO A WEAK VALUE FOR DATASETS INCLUDING LOOPS (ex: 3 to 5), TO AVOID GENERATING A TRAINING SET THAT IS ORDERS OF MAGNITUDE BIGGER THAN THE ORIGINAL PURE DATASET, unless done on purpose**
- (in case we wanted to eliminate non-deterministic cases) the function that filters non-deterministic questions is not perfect, it offers 'weak conditions' to remove as much 'bad' snippets as possible.
- (in case we wanted to eliminate non-deterministic cases) the errored_snippets_are_non_deterministic flag is used to whether ignore or not any code snippets that might raise exeuction errors if the masked operator is replaced with an operator other than the original.
- (in case we wanted to eliminate non-deterministic cases) different_step_answers_are_non_deterministic flag is used to whether ignore or not any code snippet whose execution might not end in the same step if the masked operator is replaced with an operator other than the original.

quick summary on how generating training data works : 
1. capture a snippet
2. execute the snippet and freeze it at a random step
3. save the variable states in that step
4. pick a random operator that can be masked 
5. now that we have the 3 components (snippet, step, operator) we build one training example by :
	1. highlighting the step by encapsulating the line with @ and $
	2. contatenate the variable states at the end of that same highlighted line
	3. replace the picked operator with a "?"
	4. at the end of the snippet add this comment "# operator?X" replacing X with the original masked operator

quick summary on the evaluation process : 
for every evaluation snippet, we do the following : 
- feed it to the model "without the label ofc" and store the predicted operator, let's call it "Z"
- extract the variable states from the snippet with regex magic "original_states"
- extract the highlighted line index "also with regex magic", stored in "lineno" variable
- transform the evaluation snippet into an executable snippet by doing the following steps
	- replace the "?" with Z
	- remove the variable states concatenated at the end of the highlighted line
	- remove @ and $ from the highlighted line
	- hide the comment at the end "# operator?X"
- now, given this new executable snippet "Modified_snippet", the old variable states "original_states" and the line index of the highlighted line "lineno" execute this evaluation algorithm
	- initialize an empty list_of_states
	- execute the snippet "modified_snippet"
		- meanwhile the execution, everytime we reach a line with an index equal to "lineno" we append the corresponding states to the list_of_states
	- if original_states is equal to one of the elements of the list_of_states, then we consider the answer as positive "correct"
	- if original_states is not equal to any of the elements of the list_of_states, then we consider the answer as negative "incorrect"


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
- ps : if we masked a value that is part of an assignement to a variable "a" for example, then the state of "a" must be masked inorder not to make the training example too easy
- **REMEMBER TO SET THE step_limit VARIABLE TO A WEAK VALUE FOR DATASETS INCLUDING LOOPS (ex: 3 to 5), TO AVOID GENERATING A TRAINING SET THAT IS ORDERS OF MAGNITUDE BIGGER THAN THE ORIGINAL PURE DATASET, unless done on purpose**

training data generation process : 
- take the pure snippet
- execute till a specific step and save the line index of the coresponding step
- save the variable states at that step
- pick a random initialisation line
- mask one number in that initialisation by replacing it with '?' -save the masked value before masking of course-
- save the corresponding variable name as well (so in : "a = 12 + ?" the corresponding variable is 'a')
- highlight the step at which we stopped executing "encapsulating with @ and $"
- concatenate that step with the variable states "but this time the state of the corresponding variable is masked too, using '~' "
- and finally append this comment at the end "# input?X" X being the masked value

evaluation process: 
- from the evaluation sample capture the following info : 
	- the value that the model predicted
	- the highlighted line index
	- the original state of the variables corresponding to the the highlighted line
	- a modified version of the snippet where the input is replaced with what the model has predicted
- now execute the modified version of the snippet
- everytime the debugger passes by the highlighted line, append the state of the variables in a states list
- after the execution check whether the original variable states are equal to at least one of the elements in the list "ignoring the masked variable's state in the process"
- if at least one match is found, then the model has a correct answer, else, the answer is false

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
