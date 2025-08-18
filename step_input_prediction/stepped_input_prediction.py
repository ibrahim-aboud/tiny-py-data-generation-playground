import os
import ast
import random
import sys
from tqdm import tqdm
from io import StringIO
from contextlib import redirect_stdout




#____________________Hyper Parameters________________________#
source_file_path = "sample_snippets.txt"
destination_file_path = "stepped_input_prediction.txt"
step_limit = 10 # how many steps to sample from each code snippet (0 means no limit)
sampling_limit = 3 # how many individual maskings can we generate from each snippet (0 means no limit)


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
    # Check runtime value range

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




def collect_candidates(tree):
    """
    Collect numeric values (positive and negative) from assignments and binary ops,
    along with the corresponding affected variable names.
    """
    candidates = []
    variables = []

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            val = stmt.value
            # Assignment target(s) — handle single and tuple targets
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                target_var = stmt.targets[0].id
            else:
                target_var = None  # you can extend logic if you want tuple unpacking, etc.

            # Case: x = constant
            if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                candidates.append(val)
                variables.append(target_var)

            # Case: x = negative constant
            elif isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub) and isinstance(val.operand, ast.Constant):
                candidates.append(val)
                variables.append(target_var)

            # Case: binary operations
            elif isinstance(val, ast.BinOp):
                for side in (val.left, val.right):
                    if isinstance(side, ast.Constant) and isinstance(side.value, (int, float)):
                        candidates.append(side)
                        variables.append(target_var)
                    elif isinstance(side, ast.UnaryOp) and isinstance(side.op, ast.USub) and isinstance(side.operand, ast.Constant):
                        candidates.append(side)
                        variables.append(target_var)
        else:
            break

    return candidates, variables

def mask_node(tree, target_node):
    """Replace target_node with a bare name '?'."""
    class ReplaceTransformer(ast.NodeTransformer):
        def visit(self, node):
            if node is target_node:
                return ast.Name(id="?", ctx=ast.Load())
            return super().visit(node)

    ReplaceTransformer().visit(tree)
    ast.fix_missing_locations(tree)

def mask_all_values_ast(code):
    """Return list of (masked_code, original_value, line_number) for each numeric candidate."""
    tree = ast.parse(code)
    candidates, _ = collect_candidates(tree)
    results = []

    for idx, candidate in enumerate(candidates):
        # Copy the AST fresh for each masking
        tree_copy = ast.parse(code)

        # Locate the same candidate in the fresh tree
        fresh_candidates, affected_variables = collect_candidates(tree_copy)
        target_node = fresh_candidates[idx]

        # Extract value
        if isinstance(target_node, ast.Constant):
            original_value = target_node.value
        elif isinstance(target_node, ast.UnaryOp):
            original_value = -target_node.operand.value
        else:
            original_value = None

        # Line number (1-based from AST)
        line_number = getattr(target_node, "lineno", None)

        # Mask and unparse
        mask_node(tree_copy, target_node)
        masked_code = ast.unparse(tree_copy)

        results.append((masked_code, original_value, line_number, affected_variables[idx]))

    return results


def sample_unique(line_num, count, n):
    # Build the interval [line_num+1, count] inclusive
    interval = range(line_num + 1, count + 1)
    if n!=0:
        # Clamp n to the size of the interval
        n = min(n, len(interval))

        return random.sample(interval, n)
    else:
        return interval
    

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
        return ''

    if len(trace) != 0:
        return trace[0],trace[1]
    else:
        return '',0
    
def mask_variable_value(variable_states, var_name):
    """
    Given a state string like 'a?2;b?5;c?9' and a variable name,
    replace the value of that variable with '~'.
    """
    parts = variable_states.split(";")
    masked_parts = []
    
    for part in parts:
        if "?" not in part:
            continue
        var, val = part.split("?", 1)
        if var == var_name:
            masked_parts.append(f"{var}?~")
        else:
            masked_parts.append(part)
    
    return ";".join(masked_parts)

def generate_stepped_input_prediction_snippet(code_snippet,step_limit=10,sampling_limit=0):

    
    
    code_snippet = code_snippet.strip('\n')
    count = line_counter(code_snippet)
    masked_list = mask_all_values_ast(code_snippet)
    if sampling_limit != 0 and sampling_limit<len(masked_list):
        masked_list = random.sample(masked_list)
    results = []
    for masked_code, original_value, line_num, target_var in masked_list:
        if line_num == count:
            continue
        possible_steps = sample_unique(line_num,count, step_limit)
        for step in possible_steps:
            variable_states, highlighted_line_nb = get_variable_values_from_code_step(code_snippet,step,stack)
            if variable_states:
                masked_code_lines = masked_code.split('\n')
                masked_code_lines[highlighted_line_nb] ="@" + masked_code_lines[highlighted_line_nb] + "$" + mask_variable_value(variable_states,target_var)
                masked_code_final = '\n'.join(masked_code_lines)
                masked_code_final = masked_code_final+ "\n# input?" + str(original_value)
                results.append(masked_code_final)

    return results



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
            snippets = generate_stepped_input_prediction_snippet(snippet,step_limit,sampling_limit)
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