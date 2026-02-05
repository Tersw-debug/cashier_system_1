import customtkinter
from tkinter import CENTER
from UI.login_ui import login_ui
from PIL import Image
import os

def show_login(root):

    customtkinter.set_appearance_mode("dark")  # or "dark"
    customtkinter.set_default_color_theme("blue")

    appearance = customtkinter.get_appearance_mode()
    bg_color = "#121212" if appearance == "Dark" else "#f4f6f8"
    card_color = "#1e1e1e" if appearance == "Dark" else "#ffffff"
    text_color = "#ffffff" if appearance == "Dark" else "#000000"


    main_container = customtkinter.CTkFrame(root, fg_color=bg_color)
    main_container.pack(fill="both" ,expand=True)

    main_container.grid_columnconfigure(0,weight=3)
    main_container.grid_columnconfigure(1,weight=2)
    main_container.grid_rowconfigure(0, weight=1)

    # Background frame (optional, helps contrast)
    left = customtkinter.CTkFrame(main_container, fg_color=bg_color)
    left.grid(row=0, column=0, sticky="nsew")
    left.grid_propagate(False)



    right = customtkinter.CTkFrame(main_container, fg_color=bg_color, width=400)
    right.grid(row=0, column=1, sticky="ns")
    # Card
    frame = customtkinter.CTkFrame(
        right,
        width=400,
        height=450,
        fg_color=card_color,
        bg_color=bg_color
    )
    frame.pack(fill="both",expand=True)
    frame.pack_propagate(False)

    # Title
    frame_content = customtkinter.CTkFrame(
        frame,
        width=360,       # give width
        height=500,      # give height
        fg_color=card_color,
        bg_color=bg_color
    )

    frame_content.place(relx=0.5, rely=0.5, anchor='center')
    frame_content.pack_propagate(False)

    customtkinter.CTkLabel(
        frame_content,
        text="Welcome Back",
        font=("Segoe UI", 26, "bold"),
        text_color=text_color
    ).pack(pady=(30, 10))


    

    customtkinter.CTkLabel(
        frame_content,
        text="Login to your account",
        font=("Segoe UI", 13),
        text_color="#777"
    ).pack(pady=(0, 25))

    # Username
    customtkinter.CTkLabel(
        frame_content,
        text="Username",
        font=("Segoe UI", 12, "bold"),
        text_color="#777"
    ).pack(anchor="w", padx=40)

    e1 = customtkinter.CTkEntry(
        frame_content,
        width=320,
        height=40,
        corner_radius=10,
        font=("Segoe UI", 13),
        placeholder_text="Enter your username"
    )
    e1.pack(pady=(6, 15))

    # Password
    customtkinter.CTkLabel(
        frame_content,
        text="Password",
        font=("Segoe UI", 12, "bold"),
        text_color="#777"
    ).pack(anchor="w", padx=40)

    e2 = customtkinter.CTkEntry(
        frame_content,
        width=320,
        height=40,
        corner_radius=10,
        font=("Segoe UI", 13),
        placeholder_text="Enter your password",
        show="•"
    )
    e2.pack(pady=(6, 25))

    # Login button
    login_button = customtkinter.CTkButton(
        frame_content,
        text="Login",
        command=lambda: login_ui(root, e1, e2, frame),
        width=320,
        height=45,
        corner_radius=12,
        font=("Segoe UI", 16, "bold"),
        fg_color="#4f46e5",
        hover_color="#4338ca"
    )
    login_button.pack(pady=(0, 20))

    root.bind("<Return>", lambda e: login_button.invoke())
    BASE_DIR = os.path.dirname(__file__)
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    
    original_image = Image.open(os.path.join(ASSETS_DIR, "background.png"))

    
    bg_image = customtkinter.CTkImage(light_image=original_image, dark_image=original_image, size=(1, 1))
    
    bg_label = customtkinter.CTkLabel(left, text="", image=bg_image)
    bg_label.pack(fill="both", expand=True)

    def resize_image(event):
        # Calculate new dimensions to fill the frame
        new_width = event.width
        new_height = event.height
        
        # Update the CTkImage size dynamically
        bg_image.configure(size=(new_width, new_height))

    # Bind the resize function to the frame
    left.bind("<Configure>", resize_image)

    return main_container
