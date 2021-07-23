# vc.py -- wrapper for git. I never want to use git again.
#
# Roger B. Dannenberg
# June 2021

import sys
import time
import os
import subprocess
from urllib.parse import urlparse

UNMANAGED_RESPONSES = """    a - add to repo
    i - add file to ignore list
    x - add file's extension to the ignore list
    d - delete the file (after confirm)
    p - pass (do not add to repo, do nothing with file)
    ? or h or other - print this help and prompt again"""

HELP = """vc - version control. A wrapper to avoid git exposure and damage.

COMMAND SUMMARY
---------------
vc checkout url directory
    Create a local working directory (and clone) from a URL and local 
        directory name.
vc help
    Print this help.
vc info
    Get info about the repo.
vc mv <source> <destination>
vc mv <source> ... <destination directory>
    Rename file or move files, change is recorded for future push
vc new
    Given a local directory and a newly created remote repo, create a local
        repo and populate the remote repo from local files.
vc push
    Backup whole root directory from root to 
        root/../root-backups/timestamp/
    Check in (git commit -a; git push) the current files to the
         master repo.
    Always checks in files that have changed (as in git commit -a)
    Prompts for what to do with files that are not managed. 
    Responses to prompts are:
         a - add to repo
         i - add file to ignore list
         x - add file's extension to the ignore list
         d - delete the file (after confirm)
         p - pass (do not add to repo, do nothing with file)
         ? or h - print this help and prompt again
         1,2,3,... - add nth folder of this path to ignore list;
             if prompt is xyz/tmp/foo.test, '2' will add /xyz/tmp/
             to .gitignore.
vc push local
    Just like "vc push" except this checks in (git commit) 
        to local repo only.
vc pull
    Check out (git pull) from the master repo.

vc rm <file>
    Remove <file> from local repo and from local filesystem. Use push to
    update the master repo.
"""

repo_root = None


def show_help():
    print(HELP)


def get_root(suffix):
    global repo_root
    if not repo_root:
        sp = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            stdout=subprocess.PIPE)
        repo_root = sp.stdout.decode("utf-8").strip()
        if repo_root[0] != "/":
            raise Exception("Could not get root for repo")
    return repo_root + suffix


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        show_help()
        return
    # if we are supposed to be in a working directory tree, get some info:
    if sys.argv[1] not in ["checkout", "new"]:
        sp = subprocess.run(["git", "remote", "-v"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        remotes = sp.stdout.decode("utf-8").splitlines()
        errout = sp.stderr.decode("utf-8")
        if len(remotes) == 2 and remotes[0].find("origin") == 0:
            # expected in simple cases
            remote = remotes[0]
            loc2 = remote.find("(")
            if loc2 < 0:
                raise Exception("Could not make sense of remote: " + remote)
            print("- " + remote[7 : loc2])
        elif errout.find("fatal:") >= 0:
            print("- error output from git:", errout, end="")
            print("- vc: Maybe you are not in a working directory.")
            return
        else:
            for line in remotes: print("- " + remotes)

    IMPLEMENTATIONS[COMMANDS.index(sys.argv[1])](sys.argv[1:])


def show_branch():
    sp = subprocess.run(["git", "status"],
                        stdout=subprocess.PIPE)
    # first line is main or branch name:
    print("- " + sp.stdout.decode("utf-8").split('\n', 1)[0])


def make_backup():
    backups = get_root("-backups")
    if not os.path.isdir(backups):
        if os.path.isfile(backups):
            raise Exception("Unexpected file: " + backups)
        os.mkdir(backups)
    backup = backups + "/" + time.strftime("%Y%m%d-%H%M%S")
    os.mkdir(backup)
    sp = subprocess.run(["cp", "-Rp", get_root(""), backup])


def find_untracked(dryrun):
    files = []
    loc = dryrun.find("Untracked files:")
    if loc < 0:
        return files
    loc = dryrun.find("\n\n", loc)
    if loc < 0:
        raise Exception("Untracked files heading found, but no files found")
    loc += 2
    while True:
        loc2 = dryrun.find("\n", loc)
        if loc2 == loc:  # found blank line to terminate file list
            return files
        elif loc == len(dryrun):  # no blank line, but this is the end
            return files
        elif loc2 < 0:
            print("Warning: unexpected text after untracked files: |" + \
                  dryrun[loc : ] + "|, len", len(dryrun[loc : ]))
            return files
        filename = dryrun[loc : loc2].strip()
        print("Debug: adding |" + filename + "| to untracked files")
        files.append(filename)
        loc = loc2 + 1


def add_to_gitignore(text):
    with open(get_root("/.gitignore"), "a") as file_object:
        file_object.write("\n" + text + "\n")
    print('- added "' + text + '"' + " to repo's .gitignore file.")


def confirm(prompt):
    inp = input("Type Y to confirm " + prompt + ": ")
    return inp == "Y"


def delete_after_confirm(filepath):
    if confirm("delete " + filepath):
        os.remove(filepath)
        return True
    return False


def handle_untracked_file(file):
    if os.path.isdir(file):
        # it's a directory. Prompt for disposition of each file in the dir tree:
        for (dirpath, dirnames, filenames) in os.walk(file):
            for name in filenames:
                handle_untracked_file(os.path.join(dirpath, name))
        return

    inp = input("  " + file + ": [aixdph123...] ")
    if inp == "a":
        subprocess.run(["git", "add", get_root("/" + file)])
    elif inp == "i":
        add_to_gitignore("/" + file)
    elif inp == "x":
        name, ext = os.path.splitext(file)
        if len(ext) < 1 or ext[0] != ".":
            print("- this file has no extension, try again")
            handle_untracked_file(file)
        elif len(ext) > 0 and ext[-1] == "~":
            add_to_gitignore("*~")
        else:
            add_to_gitignore("*" + ext)
    elif inp == "d":
        if not delete_after_confirm(get_root("/" + file)):
            handle_untracked_file(file)
    elif inp == "p":
        pass
    elif inp.isdigit():
        folders = []
        while file != "":
            head, tail = os.path.split(file)
            folders.append(tail)
            file = head
        folders.reverse()
        inp = int(inp)
        # only allow selection of a folder on path:
        if os.path.isfile(file):
            folders.pop()  # remove file as an option
        if len(folders) < inp:
            print("- there are not", inp, "folders on path, try again")
            handle_untracked_file(file)
            return
        del folders[inp : ]
        path = folders[0]
        for folder in folders[1:]:
            path = os.path.join(path, folder)
        add_to_gitignore("/" + path + "/")
    else:
        print(UNMANAGED_RESPONSES)
        handle_untracked_file(file)
        

def local_push():
    sp = subprocess.run(["git", "commit", "-a", "--dry-run"],
                        stdout=subprocess.PIPE)
    dryrun = sp.stdout.decode("utf-8")
    untracked = find_untracked(dryrun)
    if len(untracked) > 0:
        print("- found untracked files. Specify what to do:")
        for file in untracked:
            handle_untracked_file(file)
    subprocess.run(["git", "commit", "-a"])
    

def push(args, extra_push_args = []):
    show_branch()
    # allow either "vc push local" or just "vc push":
    if (len(args) == 2 and args[1] == "local") or len(args) == 1:
        make_backup()
        local_push()
    if len(args) == 1:  # only do this if non-local
        if confirm("push to remote repo"):
            subprocess.run(["git", "fetch"])
            sp = subprocess.run(["git", "status", "-sb"],
                                stdout=subprocess.PIPE)
            out = sp.stdout.decode("utf-8")
            if out.find("behind") >= 0:
                print("- you must pull changes from the remote repo")
                print("-     before you can push any local changes")
                if confirm("pull from remote repo now"):
                    sp = subprocess.run(["git", "pull"], stdout=subprocess.PIPE)
                    out = sp.stdout.decode("utf-8")
                    print("- git output:\n", out, end="")
                    if out.find("Merge conflict") >= 0:
                        print("- automatic merge failed, so you must now",
                              "manually merge changes")
                        print("-     from the remote repo with your local",
                              "changes; then run")
                        print("-     'vc push' to finally push your changes",
                              "to the remote repo.")
                        return
                else:
                    print("- local changes are not committed to remote repo")
                    return 
            sp = subprocess.run(["git", "push"] + extra_push_args,
                                stdout=subprocess.PIPE)
            out = sp.stdout.decode("utf-8")            
            print("- git output:\n", out, end="")
            if out.find("hint: Updates were rejected because the tip of " +
                        "your current branch is behind") >= 0:
                # push failed. Give some advice:
                print("- 'vc push' did not complete because your local repo")
                print("-     is not up-to-date.")
    

def pull(args, extra_pull_args = []):
    show_branch()
    subprocess.run(["git", "pull"] + extra_pull_args)


def showinfo(args):
    subprocess.run(["git", "status"])


def newrepo(args):
    print("- you will need a URL like https://github.com/username/reponame")
    if not confirm("create local repo and initial check in"):
        print("- vc new command exited without any changes.")
        return
    subprocess.run(["git", "init"])
    # rename master to main -- less offensive, more compatible with github
    subprocess.run(["git", "checkout", "-b", "main"])
    local_push()
    url = input("URL for remote repository: ")
    subprocess.run(["git", "remote", "add", "origin", url])
    subprocess.run(["git", "fetch", "--all"])
    subprocess.run(["git", "branch", "--set-upstream-to=origin/main", "main"])
    # in case there are files already, e.g. license or README.md, pull them in
    pull([], extra_pull_args=["--allow-unrelated-histories"])
    if not os.path.isfile("README.md"):
        if confirm("create README.md"):
            with open("README.md", "w") as readme:
                readme.write("# vc")
            subprocess.run(["git", "add", "README.md"])
            subprocess.run(["git", "commit", "-m", "created README.md"])
    # subprocess.run(["git", "branch", "-M", "main"])
    push(["push"])


def checkout(args):
    """args are ['checkout', <repo url>, <local directory>]"""
    if len(args) < 3:
        url = urlparse(args[1])
        path = url[2]
        dir = os.path.split(path)
        dir = os.path.splitext(dir)[0]
        print("- derived '" + dir + "' as local directory")
    else:
        dir = args[2]
    if os.path.isdir(dir):
        raise Exception("Directory already exists: " + dir)
    subprocess.run(["git", "clone", args[1], dir])


def rename(args):
    if len(args) >= 3:
        if len(args) == 3:
            print("- rename " + args[1] + " to " + args[2])
        else:
            print("- move " + args[1:-1] + " to " + args[-1])
        subprocess.run(["git"] + args)


def remove(args):
    """Implements vc rm <file> command"""
    if len(args) == 1:
        filename = input("File to remove: ")
    elif len(args) == 2:
        filename = args[1]
    else:
        print('- command syntax is "vc rm <file-to-remove>"')
        return
    if not os.path.isfile(filename):
        print('- file ' + filename + ' does not exist')
        return
    subprocess.run(["git", "rm", filename])


COMMANDS = ["push", "pull", "info", "new", "mv", "checkout", "rm"]
IMPLEMENTATIONS = [push, pull, showinfo, newrepo, rename, checkout, remove]

main()
