# TryHackMe: Overpass

**Difficulty:** Easy  
**Focus:** Web enumeration, client-side authentication bypass, SSH key passphrase cracking, cron job abuse, and privilege escalation.

## 1. Introduction

I started the Overpass room by mapping the target IP address to `overpass.thm` in `/etc/hosts`. Then I scanned the target with Nmap and found two open ports: **22 (SSH)** and **80 (HTTP)**. Since the website was accessible, I started by exploring it before moving to the SSH service.

## 2. Nmap Scan

I ran Nmap with default scripts and service-version detection to identify the available services.

```bash
nmap -sCV overpass.thm -oN nmap_scan.txt
```

- `-sC` runs Nmap's default scripts.
- `-sV` attempts to identify service versions.
- `-oN` saves the output in normal text format.

The scan showed SSH on port 22 and HTTP on port 80. I saved the output as `nmap_scan.txt` for reference.

![Nmap scan](screenshots/overpass-1.png)

## 3. Exploring the Website

I opened `http://overpass.thm` and read the page. It described Overpass as a password manager that stores passwords using “military grade” encryption. That made me curious about how the application actually handled passwords.

![Overpass homepage](screenshots/overpass-2.png)

I also inspected the page text/source. It included a clue referring to a Roman encryption technique, which led me to research the **Caesar cipher**—a substitution cipher associated with Julius Caesar.

![Website encryption hint](screenshots/overpass-3.png)

I continued exploring the site and opened the **About Us** page. I found several usernames there and saved them for reference.

![About Us page](screenshots/overpass-4.png)

## 4. Investigating the Downloadable Application

The Downloads page provided the application and its source code, so I downloaded both to understand how the password manager worked.

![Downloads page](screenshots/overpass-5.png)

After reviewing the source code, I found that the application used **ROT47** to transform stored passwords. This was an important distinction from the Caesar-cipher clue on the website: the downloaded application’s code showed ROT47 specifically. ROT47 is a simple character-rotation obfuscation method, not secure password encryption, so anyone who knows the method can reverse it without a secret key.

![Application source code](screenshots/overpass-6.png)

I ran the application to understand its features. It allowed me to retrieve a password for a service, set or update a password, delete a password, retrieve all stored passwords, and exit.

![Running the application](screenshots/overpass-7.png)

I then checked the local `~/.overpass` file where the application stored its data. The values were encoded rather than securely encrypted. I decoded the values with ROT47 and confirmed that this matched the algorithm I had found in the source code.

![Decoded application data](screenshots/overpass-8.png)

![Stored values in the local file](screenshots/overpass-9.png)

## 5. Directory Enumeration

Next, I used Gobuster to look for additional website paths and files.

```bash
gobuster dir -u http://overpass.thm/ -w big.txt -x php,json,js,txt,html,bak --no-error
```

The scan revealed several useful paths, including `/aboutus/`, `/downloads/`, `/admin/`, and `login.js`. The `/admin/` path contained an administrator login page, so I investigated that next.

![Gobuster results](screenshots/overpass-10.png)

## 6. Investigating the Admin Login

The admin page initially showed a login form. I already had usernames from the About Us page, so I spent some time testing the login. I tried password brute-forcing and common web attacks such as SQL injection and XSS, but those attempts did not get me access.

![Admin login page](screenshots/overpass-11.png)

Rather than continuing to guess, I returned to the Gobuster results and inspected `login.js`. The code showed how the page handled the response from `/api/login`: if the response text was exactly `Incorrect credentials`, it displayed an error; otherwise, it stored the response as a `SessionToken` cookie and redirected the browser to `/admin`.

This led me to test whether the application actually validated the cookie on the server or simply trusted a cookie supplied by the browser. I set `SessionToken` to an arbitrary value and refreshed the page. The admin area opened, showing that the session/authentication check was not being properly enforced.

![Relevant login JavaScript](screenshots/overpass-13.png)

## 7. Retrieving James's SSH Private Key

Inside the admin area, I found a note addressed to James and an RSA private key. The note said that James's SSH key was protected by a passphrase, so I saved the key as `james.rsa` and tried to use it for SSH access.

![Admin area with the SSH key](screenshots/overpass-14.png)

SSH requested a passphrase, so I converted the key into a format that John the Ripper could process, then used the `rockyou.txt` wordlist to crack it.

```bash
ssh2john james.rsa > james.hash
john james.hash --wordlist=rockyou.txt
```

John recovered the passphrase: `james13`.

![Cracking the key passphrase](screenshots/overpass-15.png)

I used the private key and recovered passphrase to log in as `james`.

```bash
ssh james@overpass.thm -i james.rsa
```

After logging in, I checked the files in James's home directory and read `user.txt` to retrieve the user flag.

```bash
cat user.txt
```

![SSH login and user flag](screenshots/overpass-16.png)

## 8. Privilege Escalation Enumeration

With access as `james`, I ran LinPEAS to look for privilege-escalation opportunities. I noticed an interesting scheduled task in the system crontab, so I inspected `/etc/crontab` to understand what it was doing.

The important entry was:

```cron
* * * * * root curl overpass.thm/downloads/src/buildscript.sh | bash
```

This meant that every minute, a root-owned cron job fetched `buildscript.sh` from `overpass.thm` and immediately passed the downloaded content to Bash. Because the command ran as root, controlling the content it fetched could lead to root-level command execution.

![Cron job in the system crontab](screenshots/overpass-20.png)

## 9. Redirecting the Cron Job to My Machine

I investigated how `overpass.thm` resolved on the target and learned that its entry in `/etc/hosts` pointed to the local machine. LinPEAS also helped me identify that the hosts file was writable, which meant I could change the mapping so that `overpass.thm` resolved to my attacking machine instead.

I then created the same path that the cron job requested—`downloads/src/buildscript.sh`—on my machine. I placed a reverse-shell command in that script, using my own reachable VPN/interface IP address and listener port. The script included with this writeup reflects the callback address used in my lab session; replace it with your own address when reproducing the steps in an authorized lab.

I started a Python HTTP server on port 80 to serve the file and a Netcat listener on port 8081 to receive the connection. When the root cron job ran, it fetched my script and executed it as root, giving me a root shell.

```bash
# In the directory containing downloads/src/buildscript.sh
python3 -m http.server 80
```

In another terminal:

```bash
nc -lvnp 8081
```

![Received root shell and root flag](screenshots/overpass-18.png)

## 10. Flags

| Flag | Result |
|---|---|
| User flag | `thm{65c1aaf000506e56996822c6281e6bf7}` |
| Root flag | `thm{7f336f8c359dbac18d54fdd64ea753bb}` |

## 11. Tools Used

- Nmap — service discovery and version detection
- Gobuster — web directory and file enumeration
- Browser developer tools — JavaScript inspection and cookie testing
- `ssh2john` — converting the SSH private key to a John-compatible hash
- John the Ripper — cracking the SSH key passphrase
- LinPEAS — local privilege-escalation enumeration
- Python HTTP server — serving the replacement build script
- Netcat — receiving the reverse shell

## 12. Key Takeaways

1. **Read the source code.** The website's encryption claim did not match the weak ROT47 method used by the downloaded application.
2. **Do not trust client-side authentication logic.** A browser cookie should not grant access unless the server validates the session securely.
3. **Protect private keys.** A stolen SSH key may still be usable if its passphrase is weak enough to crack offline.
4. **Review scheduled root tasks carefully.** A root cron job that downloads a script and pipes it directly to Bash is dangerous when an attacker can influence hostname resolution or the fetched content.
5. **File permissions matter.** A writable `/etc/hosts` file allowed me to redirect the hostname used by the root cron job.

## 13. Summary

I started with the two exposed services, explored the password manager and its source code, and used Gobuster to discover the admin page. Inspecting `login.js` helped me identify the weak `SessionToken` handling and access the administrator area. From there, I recovered James's RSA key, cracked its passphrase with John, and obtained SSH access. Finally, LinPEAS led me to a root cron job that trusted a script fetched from `overpass.thm`. By redirecting that hostname to my machine and serving the expected script path, I received a root shell and retrieved the final flag.

> **Disclaimer:** This writeup documents a TryHackMe training lab. Use these techniques only in environments where you have explicit permission to test.
