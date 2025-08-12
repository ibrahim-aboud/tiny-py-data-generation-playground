import os
import ast
import random
import sys
from tqdm import tqdm
from io import StringIO
from contextlib import redirect_stdout




#____________________Hyper Parameters________________________#
source_file_path = "sample_snippets.txt"
destination_file_path = "stepped_operator_prediction.txt"
include_arithmetic_masking = True
include_comparator_masking = False
errored_snippets_are_non_deterministic = True
different_step_answers_are_non_deterministic = True
limit = 0 # How many operator masking cases to generate out of a single snippet step (0 means no limit)
sampling_limit = 3 # how many random selected steps to generate out of each snippet (0 means no limit)
# OPPOSITE_OPERATORS = { 
#     '<': ['>'],
#     '>': ['<'],
#     '+': ['-','*','/'],
#     '-': ['+','/','*'],
#     '*': ['/','+','-'],
#     '/': ['*','+','-']
# }
# USE OPPOSITE OPERATORS DEPENDING ON THE DATASET TYPE !
OPPOSITE_OPERATORS = {
    '<': ['>'],
    '>': ['<'],
    '+': ['-'],
    '-': ['+']
}
#____________________Utility Functions________________________#

def get_variable_values_from_code(code_snippet):


    # --- Step 1: Static Analysis with AST ---
    # We use ast.walk to find all variable assignments and record their
    # names in the order they first appear.
    
    ordered_variables = []
    try:
        tree = ast.parse(code_snippet)

        # adding nodes that include variable names, or assignments ..etc
        nodes = [node for node in ast.walk(tree)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)]

        # Sort by line number, then column offset
        nodes.sort(key=lambda n: (n.lineno, n.col_offset))

        ordered_variables = []
        for node in nodes:
            if node.id not in ordered_variables:
                ordered_variables.append(node.id)

    except SyntaxError as e:
        print(f"Error parsing code: {e}")
        return None

    # --- Step 2: Dynamic Execution ---
    # We execute the code in a controlled environment to capture the final
    # state of the variables.
    
    # This dictionary will act as the local scope for the executed code.
    local_scope = {}
    try:
        # The exec() function runs the Python code. The second argument
        # is the global scope (we leave it empty) and the third is the
        # local scope, which will be populated by the code.
        exec(code_snippet, {}, local_scope)
    except Exception as e:
        return None

 
    if not ordered_variables:
        print("No variable assignments found.")
        return None


    variable_dictionary = []

    for var_name in ordered_variables:
        if var_name in local_scope:
            # Retrieve the final value from the scope dictionary.
            last_value = local_scope[var_name]
            variable_dictionary.append((var_name,last_value))

        #else:
            # This case is rare but could happen if a variable is declared
            # in a scope that doesn't persist, e.g., a list comprehension.
            #variable_dictionary.append((var_name,None))


    return variable_dictionary

def find_operator_location(code_line, left_end_col, right_start_col):
    # given a code line, and the delimiters of an expression in that code line
    # the function returns the exact location of the operator "aka column index" relative to the code line
    search_slice = code_line[left_end_col:right_start_col]
    for i, char in enumerate(search_slice):
        if not char.isspace():
            return left_end_col + i
    return -1


def get_verified_lines(code):
    # given a code snippet, return a list of all line indexes
    # that have been reached during the execution of the snippet
    # lines that are not reached include lines within if-blocks 
    # that have a 'false' condition

    # using a set() to avoid redunduncy
    verified_lines = set()

    def trace_lines(frame, event, arg):
        if event == "line":
            lineno = frame.f_lineno
            verified_lines.add(lineno)
        return trace_lines

    sys.settrace(trace_lines)
    try:
        exec(code, {})
    finally:
        sys.settrace(None)

    return verified_lines

def get_verified_lines_till_step(code,max_reached_line_nb,keep_last_reached_line):
    ## MAX_REACHED_LINE_NB MUST BE 1 BASED (first line is 1)
    verified = get_verified_lines(code)
    if keep_last_reached_line: 
        return {x for x in verified if x<=max_reached_line_nb}
    else:
        return {x for x in verified if x<max_reached_line_nb}

def find_operators_to_replace(code_snippet,verified_lines):
    # given a code snippet, the code returns a list of
    # all operators (arithmetic/comparative) that can
    # be masked to be later guessed by the model
    # returns list of tuples containing info related 
    # to the operator : (operator, column_index, line_index)
    try:
        tree = ast.parse(code_snippet)
    except SyntaxError as e:
        print(f"Error: Invalid Python code provided. {e}")
        return code_snippet

    candidates = []
    for node in ast.walk(tree):
        if hasattr(node, 'lineno') and node.lineno in verified_lines:
            if isinstance(node, ast.BinOp) and include_arithmetic_masking:
                candidates.append(node)
            elif isinstance(node, ast.Compare) and include_comparator_masking:
                candidates.append(node)

    if not candidates:
        return []

    operators = []
    code_lines = code_snippet.splitlines()



    for target_node in candidates:
        
        target_line_index = target_node.lineno - 1

        op_col = -1

        if isinstance(target_node, ast.BinOp):
            op_col = find_operator_location(
                code_lines[target_line_index],
                target_node.left.end_col_offset,
                target_node.right.col_offset
            )
        elif isinstance(target_node, ast.Compare):
            op_col = find_operator_location(
                code_lines[target_line_index],
                target_node.left.end_col_offset,
                target_node.comparators[0].col_offset
            )

        if op_col != -1:
            line = code_lines[target_line_index]
            operators.append( (line[op_col], op_col, target_line_index))

    return operators

def get_variable_values_from_code_step(code_snippet,step,stack):
    trace = []
    indented = "\n".join([f"	{line}" for line in code_snippet.split("\n")])
    func = "def func():\n" + indented 
    exec_env = func + stack

    try:
        exec(exec_env, {
            "__builtins__": __builtins__,
            "code": code_snippet,
            "trace": trace,
            "step": step,
        })
    except Exception as e:
        return '', -1

    if len(trace) != 0:
        return trace[0], trace[1]
    else:
        # the code exeuction did not reach the step
        return '', -2



def is_deterministic(code_snippet, column, line, new_operators, original_states, original_highlighted_line, step, stack):
    # given a code snippet, the old operator's location and the new operator
    # verify whether replacing the old operator with the new ones causes
    # a different execution outcome, if it does, this means that
    # guessing the masked operator is possible, if not this means that
    # multiple operators can lead to the same outcome, making the deterministic guess impossible
    for candidate_operator in new_operators:
        modified_code = replace_operator_with_symbol(code_snippet, column,line, candidate_operator)
        modified_output, new_highlighted_line = get_variable_values_from_code_step(modified_code,step,stack)
        if new_highlighted_line == -1 and errored_snippets_are_non_deterministic:
            # case 1 : error while executing the new code
            return False
        elif new_highlighted_line == -2 and different_step_answers_are_non_deterministic:
            # case 2 : did not reach the number of steps required
            return False
        else:
            # case 3 : the code reached the number of steps required and has actual variable states
            if modified_output == original_states or new_highlighted_line != original_highlighted_line:
                return False
    return True

def replace_operator_with_symbol(code_snippet, op_col, op_line,symbol):
    # given a code snippet, and a target location, the code
    # replaces the character (in our case operator) at the specfied location
    # with a symbol provided in the parameters
    code_lines = code_snippet.splitlines()
    line = code_lines[op_line]
    modified_line = line[:op_col] + symbol + line[op_col + 1:]
    code_lines[op_line] = modified_line
    return "\n".join(code_lines)


def line_counter(code_snippet):
        """
        this function counts how many lines of code in total have been executed 
        the function follows the following rules :
            - a line is not counted if :
                - it falls in a condition bloc where the condition is not verified
                - it falls in a loop where the number of iterations is equal to zero
            - a line is counted as much as it has been iterated through "if it sits in a for loop bloc for example "
        """
        counter = 0

        def trace_lines(frame, event, arg):
            nonlocal counter # declaring the outer variable
            if event == 'line': # every time the tracer detects the execution of a line of code
                filename = frame.f_code.co_filename
                if filename == '<string>' : # counting only the lines that are in the code snippet we provided "and not in some other internal libraries"
                    counter += 1 # increment the global counter
            return trace_lines


        # Set the trace function
        sys.settrace(trace_lines)

        # Capture the output of the program.
        SIO = StringIO()
        with redirect_stdout(SIO):
            # executing the code, the execution is being traced by the trace_lines() function that has been set previously
            exec(code_snippet,{'__file__': '<string>'}) # Execute the code and setting the "fake file" name to <string> so that we can recognise this code snippet later in trace_lines()

        # Disable the trace function
        sys.settrace(None)

        return counter


def generate_stepped_operator_prediction_snippet(code_snippet, operator_dictionary,limit=0,sampling_limit=0):
    # given a code snippet, return all possible training instances
    # for the stepped operator prediction task, in a list
    code_snippet = code_snippet.strip('\n')
    # Prepare the execution environment by putting the code snippet inside a function and setting up a Python trace function
    indented = "\n".join([f"	{line}" for line in code_snippet.split("\n")])
    func = "def func():\n" + indented 

    stack = """
from sys import settrace
code_lines = code.split("\\n")

counter = 0  
lineno_limit = 0
iterated_end = False

def line_tracer(frame, event, arg):
    global counter
    global lineno_limit
    global iterated_end
    current_step = list(code_lines)

    state_fill = ";".join([f"{key}?{value:}" for key, value in frame.f_locals.items()])
    if event == "line":
        if(lineno_limit > frame.f_lineno-2):
            iterated_end=True
        elif(lineno_limit < frame.f_lineno-2):
            iterated_end=False
            lineno_limit = frame.f_lineno-2
        counter +=1
        if(counter == step):
            current_step[frame.f_lineno - 2] = "@" + current_step[frame.f_lineno - 2] + "$" + state_fill
            trace.append(state_fill)
            trace.append(frame.f_lineno-2)
            trace.append(lineno_limit)
            trace.append(iterated_end)
    return line_tracer

def global_tracer(frame, event, arg):
    return line_tracer

settrace(global_tracer)
try:
    func()
finally:
    settrace(None)"""


    exec_env = func + stack
    trace_limit = line_counter(code_snippet)
    possible_lines = list(range(1,trace_limit+1))
    if sampling_limit >0 and sampling_limit < trace_limit:
        possible_lines = random.sample(possible_lines,sampling_limit)
    total_snippets = []
    for sample_line in possible_lines: 
        trace = []

        exec(exec_env, {
            "__builtins__":__builtins__, 
            "code": code_snippet,
            "trace": trace,
            "step": sample_line,
            }
        )

        variable_states = trace[0]
        highlighted_line_nb = trace[1]
        max_reached_line_nb = trace[2]
        keep_last_reached_line = trace[3]


        verified_lines = get_verified_lines_till_step(code_snippet ,max_reached_line_nb+1,keep_last_reached_line)

        candidates = find_operators_to_replace(code_snippet,verified_lines)

        if limit == 0 or limit>=len(candidates):
            selected = candidates
        else:
            selected = random.sample(candidates, limit)

        code_snippets = []

        # if variables states are not an empty string
        if variable_states:
            for candidate in selected:
                op, col, line = candidate
                if (is_deterministic(code_snippet,col,line,operator_dictionary.get(op),variable_states,highlighted_line_nb,sample_line,stack)):
                    modified_code = replace_operator_with_symbol(code_snippet,col,line,'?')
                    modified_code_lines = modified_code.split('\n')
                    modified_code_lines[highlighted_line_nb] = "@" + modified_code_lines[highlighted_line_nb] + "$" + variable_states
                    modified_code = '\n'.join(modified_code_lines)
                    modified_code = modified_code + "\n# operator?" + op
                    code_snippets.append(modified_code)


        total_snippets.extend(code_snippets)
    
    return total_snippets






#__________________MAIN_________________________


if __name__ =="__main__":

    print("--- Splitting original file content ---\n")
    with open(source_file_path, 'r', encoding='utf-8') as f:
        # read the file
        content = f.read()
        
        # extract the code snippets in the form of a list
        snippet_list = content.split('\n\n')

        # --- Output Results ---
        print(f"Successfully split the file into {len(snippet_list)} snippets.")

    transformed_snippets = []
    log = []
    index = -1
    for snippet in tqdm(snippet_list, desc="Processing Snippets"):
        index += 1
        try:
            exec(snippet, {})
            snippets = generate_stepped_operator_prediction_snippet(snippet,OPPOSITE_OPERATORS,limit=limit,sampling_limit=sampling_limit)
            log.append(str(index)+' '+str(len(snippets)))
            transformed_snippets.extend(snippets)
        except Exception:
            log.append(str(index)+' 0')
            continue  # skip invalid snippet
    print("generated :",len(transformed_snippets)," snippets")
    print("Writing...")
    with open(destination_file_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(transformed_snippets))
    with open("log_file.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print("Done, sucessfully written to :"+destination_file_path)