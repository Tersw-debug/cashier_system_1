import customtkinter
from tkinter import *

class BaseWindow(customtkinter.CTk):
    def __init__(self, title_text="System"):
        super().__init__()
        self._is_fullscreen = True
        self.prev_geometry = ""
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry("%dx%d" % (width, height))
        self.overrideredirect(True)

        self.title_bar= Frame(self, bg='darkgreen')
        self.title_bar.pack(side=TOP, fill=X)

                
        self.title_label = Label(
            self.title_bar,
            text=f"  {title_text}",
            bg="darkgreen",
            fg="white",
            font=("Arial", 12, "bold")
        )
        self.title_label.pack(side=LEFT, pady=5)

        
        self.btn_frame = Frame(self.title_bar, bg="darkgreen")
        self.btn_frame.pack(side=RIGHT)

        min_btn = Button(
            self.btn_frame,
            text=" — ",
            bg="darkgreen",
            fg="white",
            bd=0,
            font=("Arial", 12),
            command=self.minimize_window
        )
        min_btn.pack(side=LEFT, padx=2)


        max_btn = Button(
            self.btn_frame,
            text=" ☐ ",
            bg="darkgreen",
            fg="white",
            bd=0,
            font=("Arial", 12),
            command=self.toggle_fullscreen
        )
        max_btn.pack(side=LEFT, padx=2)

        close_btn = Button(
            self.btn_frame,
            text=" X ",
            bg="red",
            fg="white",
            bd=0,
            command=self.destroy
        )
        close_btn.pack(side=LEFT, padx=4)

        
        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<ButtonRelease-1>", self.stop_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)

        self.bind("<Map>", self.restore_window)
        self.title_label.bind("<ButtonPress-1>", self.start_move)
        self.title_label.bind("<ButtonRelease-1>", self.stop_move)
        self.title_label.bind("<B1-Motion>", self.do_move)


                
    def minimize_window(self):
        self.overrideredirect(False)
        self.update_idletasks()
        self.iconify()

    def restore_window(self, event=None):
        self.after(10, lambda: self.overrideredirect(True))
        self.lift()



    def toggle_fullscreen(self):
        if self.state() == "zoomed":
            self.state("normal")
        else:
            self.overrideredirect(False)
            self.state("zoomed")

        

    def start_move(self,event):
        self.x = event.x
        self.y = event.y

    def stop_move(self ,event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")


