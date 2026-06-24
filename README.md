# Visa Appointment Notification Python Script

This repository aims to use 

## Environment Variables: 

In the repository's root directory, create a file called `.env` and input the following information:

```bash
SENDER_EMAIL=<email_address_of_email_sender>
SENDER_PASSWORD=<application_password_token_of_above> # Instructions below on how to get.
RECEIVER_EMAIL=<email_addr1>;<email_addr2> # Semicolon-delimited list. 
LOGIN_EMAIL=<email_of_applicant>
LOGIN_PASSWORD=<applicant_password>
```

## Installing dependencies

First, create a python virtual environment then install dependencies in the requirements file: 

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the script

Finally, once you have set your environment and installed all pip dependencies, simply run: 

`python visa-login.py`

To run in the background and to continue running after the shell session ends: 

`nohup python visa-login.py > nohup.out &`

