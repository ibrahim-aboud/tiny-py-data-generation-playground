import os
import ast
import random
import sys
from tqdm import tqdm



#____________________Hyper Parameters________________________#
source_file_path = "sample_snippets.txt"
destination_file_path = "operator_prediction.txt"
include_arithmetic_masking = True
include_comparator_masking = False
OPPOSITE_OPERATORS = {
    '<': '>',
    '>': '<',
    '+': '-',
    '-': '+'
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



def find_operators_to_replace(code_snippet):
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

    verified_lines = get_verified_lines(code_snippet)
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


def is_deterministic(code_snippet, column, line, new_operator):
    # given a code snippet, the old operator's location and the new operator
    # verify whether replacing the old operator with the new ones causes
    # a different execution outcome, if it does, this means that
    # guessing the masked operator is possible, if not this means that
    # multiple operators can lead to the same outcome, making the deterministic guess impossible
    original_output = get_variable_values_from_code(code_snippet)
    modified_code = replace_operator_with_symbol(code_snippet, column,line, new_operator)
    modified_output = get_variable_values_from_code(modified_code)
    return modified_output != original_output

def replace_operator_with_symbol(code_snippet, op_col, op_line,symbol):
    # given a code snippet, and a target location, the code
    # replaces the character (in our case operator) at the specfied location
    # with a symbol provided in the parameters
    code_lines = code_snippet.splitlines()
    line = code_lines[op_line]
    modified_line = line[:op_col] + symbol + line[op_col + 1:]
    code_lines[op_line] = modified_line
    return "\n".join(code_lines)


def generate_operator_prediction_snippet(code_snippet, opposition_dictionary, limit = 0):
    # given a code snippet, return all possible training instances
    # for the operator prediction task, in a list

    # start with an empty list
    code_snippets = []

    # find all operators that can be masked
    candidates= find_operators_to_replace(code_snippet)


    # check if there is any limit to how many instances extracted from the snippet
    # 0 means no limit
    if limit ==0 or limit>=len(candidates):
        selected = candidates
    else:
        selected = random.sample(candidates, limit)

    # get the variable states at the end of execution
    values = get_variable_values_from_code(code_snippet)

    if values !=None :
        for candidate in selected:
            op, col, line = candidate
            if (is_deterministic(code_snippet, col, line, opposition_dictionary.get(op))):
                # for every "accepted" operator, we will build a 
                modified_code = replace_operator_with_symbol(code_snippet,col,line,'?')
                modified_code = modified_code + "\n# " + ";".join(f"{char}?{num}" for char, num in values)
                if values :
                    modified_code+=';'
                modified_code = modified_code + "operator?" + op
                code_snippets.append(modified_code)

    return code_snippets



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
    for snippet in tqdm(snippet_list, desc="Processing Snippets"):
        try:
            exec(snippet, {})
            transformed_snippets.extend(generate_operator_prediction_snippet(snippet,OPPOSITE_OPERATORS))
        except Exception:
            continue  # skip invalid snippet

    print("Writing...")
    with open(destination_file_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(transformed_snippets))
    print("Done, sucessfully written to :"+destination_file_path)