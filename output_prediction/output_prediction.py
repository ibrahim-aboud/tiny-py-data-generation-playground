import os
import ast
import random
import sys
from tqdm import tqdm



#____________________Hyper Parameters________________________#
source_file_path = "sample_snippets.txt"
destination_file_path = "output_prediction.txt"
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

def generate_output_prediction_snippet(code_snippet):
    # given a code_snippet, build an output prediction snippet
    # by appending to the existing code comments including
    # the variables states at the end of code_snippet

    values = get_variable_values_from_code(code_snippet)
    # if we do not get any syntax errors and at least one variable is visible
    if values != None and values != []:
        return code_snippet + "\n# " + ";".join(f"{char}?{num}" for char, num in values)
    return None


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
            generated_sample = generate_output_prediction_snippet(snippet)
            if generated_sample  != None:
                transformed_snippets.append(generated_sample)
        except Exception:
            continue  # skip invalid snippet

    print("Writing...")
    with open(destination_file_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(transformed_snippets))
    print("Done, sucessfully written to :"+destination_file_path)