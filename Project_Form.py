import tkinter as tk
from tkinter import messagebox
try:
    from PIL import Image, ImageTk
except ImportError:
    COLOR_BG = "#1a1a1a"
from Tapi_Project_GA_Engine import Run_GA
from Tapi_Project_Solver_Engine import Run_Solver


def on_solve_click():
    Input_file_name = Input_File_Name_TextBox.get()
    Output_file_name = Output_File_Name_TextBox.get()

    if not Input_file_name and not Output_file_name:
        messagebox.showwarning("Input_Error", "Dear student, please enter both input and output file names before clicking Solve")
        return
    elif not Input_file_name:
        messagebox.showwarning("Input_Error", "Dear student, please enter the input file name before clicking Solve")
        return
    elif not Output_file_name:
        messagebox.showwarning("Input_Error", "Dear student, please enter the output file name before clicking Solve")
        return

    if GA_CheckBox_Value.get() == 1:
        Run_GA(Input_file_name, Output_file_name)
    else:
        Run_Solver(Input_file_name, Output_file_name)


Tapi_2_Form = tk.Tk()
Tapi_2_Form.title("TAPI Project 2026_B - Genetic Algorithm")
Tapi_2_Form.geometry("800x600")



try:
    bg_image = Image.open("GA_Picture.PNG") 
    bg_image = bg_image.resize((800, 600)) 
    bg_photo = ImageTk.PhotoImage(bg_image)
    background_label = tk.Label(Tapi_2_Form, image=bg_photo)
    background_label.place(x=0, y=0, relwidth=1, relheight=1) 
    COLOR_BG = "#1a1a1a"
except:
    Tapi_2_Form.configure(bg="#a5dad9")
    
GA_Row_Frame = tk.Frame(Tapi_2_Form, bg=COLOR_BG)
GA_Row_Frame.pack(pady = (20, 10))
GA_CheckBox_Value = tk.IntVar()

def toggle_check(event):
    GA_CheckBox.toggle()

GA_Label = tk.Label(GA_Row_Frame, text="Run Genetic Algorithm?", 
                    font=("Arial", 10), fg="white", bg=COLOR_BG, cursor="hand2")
GA_Label.pack(side="left")

GA_Label.bind("<Button-1>", toggle_check)

GA_CheckBox = tk.Checkbutton(GA_Row_Frame, variable=GA_CheckBox_Value, bg=COLOR_BG, selectcolor="#FFFFFF", 
                             activebackground=COLOR_BG, highlightthickness=0, bd=0, cursor="hand2")
GA_CheckBox.pack(side="left", padx=5)

label_instruction = tk.Label(Tapi_2_Form, text="Enter input file name:", font=("Arial", 10, "bold"),
                             fg="white", bg=COLOR_BG)
label_instruction.pack(pady=0)

Input_File_Name_TextBox = tk.Entry(Tapi_2_Form, width=40, font=("Arial", 10), bg=COLOR_BG, fg="white",
                             insertbackground="white", highlightthickness=0, bd=0)
Input_File_Name_TextBox.insert(0, "") 
Input_File_Name_TextBox.pack(pady=5)



label_instruction = tk.Label(Tapi_2_Form, text="Enter output file name:", font=("Arial", 10, "bold"),
                             fg="white", bg=COLOR_BG)
label_instruction.pack(pady=0)

Output_File_Name_TextBox = tk.Entry(Tapi_2_Form, width=40, font=("Arial", 10), bg=COLOR_BG, fg="white",
                             insertbackground="white", highlightthickness=0, bd=0)
Output_File_Name_TextBox.insert(0, "") 
Output_File_Name_TextBox.pack(pady=5)

Solve_Button = tk.Button(Tapi_2_Form, text="Solve", command=on_solve_click, bg="#0DDF65", width=15, height=2)
Solve_Button.pack(side="bottom", pady=40)

Tapi_2_Form.mainloop()