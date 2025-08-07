import os
import ast
import random
import sys
from tqdm import tqdm
from io import StringIO
from contextlib import redirect_stdout



#____________________Hyper Parameters________________________#
source_file_path = "sample_snippets.txt"
destination_file_path = "line_execution_counting.txt"
#____________________Utility Functions________________________#

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


def generate_line_execution_count_snippet(code_snippet):
    # given a code_snippet, build a line execution count snippet
    # by appending to the existing code comments including
    # the number of lines executed 

    count = line_counter(code_snippet)
    return code_snippet + "\n# " + "count?"+str(count)


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
            generated_sample = generate_line_execution_count_snippet(snippet)
            if generated_sample  != None:
                transformed_snippets.append(generated_sample)
        except Exception as e:
            continue  # skip invalid snippet

    print("Writing...")
    with open(destination_file_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(transformed_snippets))
    print("Done, sucessfully written to :"+destination_file_path)