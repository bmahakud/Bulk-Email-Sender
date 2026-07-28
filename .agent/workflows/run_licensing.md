---
description: How to run the license server, activate the desktop app, and compile to an executable
---
This workflow provides step-by-step instructions on how to use the time-limited licensing system you integrated.

## Step 1: Start the Web Admin Licensing Server
The licensing server holds the registry of valid license keys, handles hardware-locking, and issues secure activation tokens.

1. Ensure Flask is installed on your server or test environment:
   ```bash
   pip install flask requests
   ```
2. Start the web admin licensing portal application:
   ```bash
   python3 licensing_server/app.py
   ```
3. Open your browser and navigate to:
   [http://localhost:5000/admin](http://localhost:5000/admin)
4. Create a new license key by typing the client's name and selecting the usage validity (e.g., 30 Days).
5. Copy the generated license key (looks like `PM-XXXX-XXXX-XXXX`).

## Step 2: Run the Desktop Application (ProMailer Pro)
Whenever the desktop application is opened:
1. Start the application:
   ```bash
   python3 run_pro.py
   ```
2. Because it has not been activated, a **License Activation Window** will automatically pop up.
3. Paste the generated license key from the Admin Portal into the input field.
4. Set the activation server URL (defaulting to `http://localhost:5000` for local testing).
5. Click **Activate Software**.
6. Once successful, the app saves the activation state locally to its database and grants full access to the Main Workspace.

## Step 3: Compiling for Windows or Linux using PyArmor (Obfuscation)
To protect your code from decompilation (preventing clients from bypassing your licensing check):

1. Install PyArmor and PyInstaller:
   ```bash
   pip install pyarmor pyinstaller
   ```
2. Obfuscate your entry script (`run_pro.py`) and standard backend modules:
   ```bash
   pyarmor pack -e " --onefile --noconsole --name ProMailer" run_pro.py
   ```
   *Note: This generates a protected executable in the `dist/` directory that contains the cryptographic verification module, completely hidden from reverse-engineering.*
