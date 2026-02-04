import customtkinter
from tkinter import CENTER
from UI.login_ui import login_ui
from PIL import Image
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
    main_container.grid_columnconfigure(1,weight=1)
    main_container.grid_rowconfigure(0, weight=1)

    # Background frame (optional, helps contrast)
    left = customtkinter.CTkFrame(main_container, fg_color=bg_color)
    left.grid(row=0, column=0, sticky="nsew")


    right = customtkinter.CTkFrame(main_container, fg_color=bg_color)
    right.grid(row=0, column=1, sticky="nsew")
    # Card
    frame = customtkinter.CTkFrame(
        right,
        width=420,
        height=360,
        corner_radius=20,
        fg_color=card_color,
        bg_color=bg_color
    )
    frame.pack(expand=True)
    frame.pack_propagate(False)

    # Title
    customtkinter.CTkLabel(
        frame,
        text="Welcome Back",
        font=("Segoe UI", 26, "bold"),
        text_color=text_color
    ).pack(pady=(30, 5))

    customtkinter.CTkLabel(
        frame,
        text="Login to your account",
        font=("Segoe UI", 13),
        text_color="#777"
    ).pack(pady=(0, 25))

    # Username
    customtkinter.CTkLabel(
        frame,
        text="Username",
        font=("Segoe UI", 12, "bold"),
        text_color="#777"
    ).pack(anchor="w", padx=40)

    e1 = customtkinter.CTkEntry(
        frame,
        width=320,
        height=40,
        corner_radius=10,
        font=("Segoe UI", 13),
        placeholder_text="Enter your username"
    )
    e1.pack(pady=(6, 15))

    # Password
    customtkinter.CTkLabel(
        frame,
        text="Password",
        font=("Segoe UI", 12, "bold"),
        text_color="#777"
    ).pack(anchor="w", padx=40)

    e2 = customtkinter.CTkEntry(
        frame,
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
        frame,
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
    """
    image = customtkinter.CTkImage(
        Image.open("assets/login.png"),
        size=(500, 500)
    )
"""
    customtkinter.CTkLabel(
        left,
        text=""
    ).pack(expand=True)

    return main_container
