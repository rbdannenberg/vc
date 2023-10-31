#!/usr/bin/env python3
# vc.py -- wrapper for git. I never want to use git again.
#
# Roger B. Dannenberg
# June 2021

import sys
import time
import os
import shutil
import subprocess
from urllib.parse import urlparse

UNMANAGED_RESPONSES = """    a - add to repo
    i - add file to ignore list
    x - add file's extension to the ignore list
    d - delete the file (after confirm)
    p - pass (do not add to repo, do nothing with file)
    p n - pass on this and everything in the nth folder
        of this path (similar to 1, 2, 3 described below)
    RETURN - if file is a directory, recurse into the directory
    ? or h or other - print this help and prompt again
    1,2,3,... - add nth folder of this path to ignore list;
        if prompt is xyz/tmp/foo.test, '2' will add /xyz/tmp/
        to .gitignore."""

HELP = """vc - version control. A wrapper to avoid git exposure and damage.

COMMAND SUMMARY
---------------
vc checkout url directory [branch]
    Create a local working directory (and clone) from a URL and local 
        directory name. Configure branch as the local branch.
vc help
    Print this help.
vc info
    Get info about the repo.
vc mv <source> <destination>
vc mv <source> ... <destination directory>
    Rename file or move files, change is recorded for future push
vc new
    Given a local directory and a newly created remote repo, create a local
        repo and populate the remote repo from local files in working directory.
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

Note: I don't want to encourage branches, but the basics are:
git branch new-branch-name -- create a new branch, do not change working branch
git checkout new-branch-name -- make new-branch-name the working branch
git checkout master -- return to master as the working branch
git merge new-branch-name -- merge new-branch-name changes into working branch
"""

repo_root = None


def show_help():
    print(HELP)


def get_root(suffix):
    global repo_root
    if not repo_root:
        sp = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        repo_root = sp.stdout.decode("utf-8").strip()
        if not os.path.isabs(repo_root):
            raise Exception("Could not get root for repo")
    return repo_root + suffix


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        show_help()
        return
    # save current directory
    original_wd = os.getcwd();
    changed_wd = False
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
        os.chdir(get_root(""))
        if original_wd != os.getcwd():
            changed_wd = True
            print("- running in repo root dir:", os.getcwd())
    IMPLEMENTATIONS[COMMANDS.index(sys.argv[1])](sys.argv[1:])
    
    if changed_wd:
        os.chdir(original_wd)
        print("- restored working directory to:", os.getcwd())


def show_branch():
    sp = subprocess.run(["git", "status"], stdout=subprocess.PIPE)
    # first line is main or branch name:
    print("- " + sp.stdout.decode("utf-8").split('\n', 1)[0])


def make_backup():
    backups = get_root("-backups")
    if not os.path.isdir(backups):
        if os.path.isfile(backups):
            raise Exception("Unexpected file: " + backups)
        os.mkdir(backups)
    backup = backups + "/" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copytree(get_root(""), backup,
                    ignore=shutil.ignore_patterns('.vs', '.git', '*.vcxproj',
                               'CMakeFiles', 'CMakeScripts', 'Debug', 
                               'Release', 'build', 'cmake_install.cmake',
                               'o2.build', 'o2.xcodeproj', 'static.cmake'))


def find_untracked(dryrun):
    files = []
    loc = dryrun.find("Untracked files:")
    if loc < 0:
        return files
    loc = dryrun.find("\n", loc)
    if loc < 0:
        raise Exception("Untracked files heading, but no end-of-line")
    loc += 1
    while True:
        loc2 = dryrun.find("\n", loc)
        # terminate file list on blank line, but only after we find at 
        # least one file:
        if len(files) > 0 and loc2 == loc:
            return files
        elif loc == len(dryrun):  # no blank line, but this is the end
            return files
        elif loc2 < 0:
            print("Warning: unexpected text after untracked files: |" + \
                  dryrun[loc : ] + "|, len", len(dryrun[loc : ]))
            return files
        filename = dryrun[loc : loc2].strip()
        # if line has only whitespace, treat it as empty line and return,
        # but only after we find at least one file
        if len(files) > 0 and len(filename) <= 0:
            return files
        elif len(filename) == 0:  # blank line or whitespace
            pass
        elif filename[0] == "(":  # assume parenthetical comment
            pass
        elif filename.find("to include in what will be committed") > 0:
            pass  # specific check for a known comment
        else:
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


pass_on_this_path = None

def handle_untracked_file(file):
    global pass_on_this_path

    if os.path.isdir(file):
        print("it's a directory...")

    if pass_on_this_path != None:
        if file.find(pass_on_this_path) == 0:
            print("pass on", file)
            return  # do nothing with this file
        else:  # we are past this folder, clear the prefix to be safe
            pass_on_this_path = None

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
        if not delete_after_confirm(file):
            handle_untracked_file(file)
    elif inp.find("p") == 0:
        if len(inp) == 1:  # just "p": pass on this file
            return
        inp = inp[1:].strip()  # remove "p and spaces
        if len(inp) == 0:  # just "p" and spaces: pass on this file
            return
        if not inp[0].isdigit():  # "p" and garbage, accept as "p"
            return
        inp = int(inp)
        folders = []
        while file != "":
            head, tail = os.path.split(file)
            folders.append(tail)
            file = head
        folders.reverse()
        # only allow selection of a folder on path
        if os.path.isfile(file):
            folders.pop()  # remove file as an option
        if len(folders) < inp:
            print("- there are not", inp, "folders on path, try again")
            handle_untracked_file(file)
            return
        del folders[inp : ]
        pass_on_this_path = folders[0]
        for folder in folders[1:]:
            pass_on_this_path = os.path.join(pass_on_this_path, folder)
        return
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
    elif os.path.isdir(file):
        print("it's a directory...")
        # it's a directory. Prompt for disposition of each file in the
        # dir tree:
        for (dirpath, dirnames, filenames) in os.walk(file):
            for name in filenames:
                handle_untracked_file(os.path.join(dirpath, name))
    else:
        print(UNMANAGED_RESPONSES)
        handle_untracked_file(file)
        

def local_push():
    sp = subprocess.run(["git", "commit", "-a", "--dry-run", "-m", "dry run"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dryrun = sp.stdout.decode("utf-8")
    dryrunerr = sp.stderr.decode("utf-8")
    untracked = find_untracked(dryrun + dryrunerr)
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
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = sp.stdout.decode("utf-8")
            if out.find("behind") >= 0:
                print("- You must pull changes from the remote repo")
                print("-     before you can push any local changes")
                if confirm("pull from remote repo now"):
                    sp = subprocess.run(["git", "pull"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    out = sp.stdout.decode("utf-8")
                    print("- git output:\n", out, "-----------------")
                    if out.find("Merge conflict") >= 0:
                        print("- Automatic merge failed, so you must now",
                              "manually merge changes")
                        print("-     from the remote repo with your local",
                              "changes; then run")
                        print("-     'vc push' to finally push your changes",
                              "to the remote repo.")
                        return
                    elif out.find("git config pull.rebase false") >= 0:
                        print("- Automatic merge failed, so you must now",
                              "manually merge changes")
                        print("-     from the remote repo with your local",
                              "changes; then run")
                        print("-     'vc push' to finally push your changes",
                              "to the remote repo.")
                        print("- Consider running the following",
                              "configuration commands:")
                        print("-         git config --global pull.rebase true")
                        print("-         git config --global fetch.prune true")
                        print("-         git config --global diff.colorMoved",
                              "zebra")
                        print("-     based on advice in")
                        print("-     spin.atomicobject.com/2020/05/05/" + \
                              "git-configurations-default")
                        return
                    elif out.find("fatal: Could not read") >= 0:
                        print('- Did git(hub) say permission "denied to"',
                              "the wrong account name?")
                        print("- If git(hub) is using the wrong account,"
                              "it may be because git")
                        print("-     has not configured your .git/config"
                              "file properly. You can")
                        print("-     specify the account to use for"
                              "authorization in the url, e.g.")
                        print('-     in .git/config under [remote ',
                              '"origin"], instead of')
                        print("-         url =",
                             "git@github.com:rbdannenberg/vc.git")
                        print("-     use")
                        print("-         url =",
                              "git@github.com-rbdannenberg:rbdannenberg/vc.git")
                        print("-     You can make this change manually"
                              "with any text editor.")
                        return
                else:
                    print("- local changes are not committed to remote repo")
                    return 
            sp = subprocess.run(["git", "push"] + extra_push_args,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = sp.stdout.decode("utf-8")            
            print("- git output:\n", out, "-----------------")
            if out.find("hint: Updates were rejected because the tip of " +
                        "your current branch is behind") >= 0:
                # push failed. Give some advice:
                print("- 'vc push' did not complete because your local repo")
                print("-     is not up-to-date.")
    

def pull(args, extra_pull_args = []):
    show_branch()
    sp = subprocess.run(["git", "pull"] + extra_pull_args,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = sp.stdout.decode("utf-8")
    print("- git output:\n", out, "-----------------")
    if out.find("signing failed") >= 0:
        print("- if git tried to use the wrong account or userid for this")
        print("-   project, edit the remote origini url in .git/config to")
        print("-   have the form git@github.com-<userid>:<userid>/<repo>.git")
        print("-   and try again.")
        

def showinfo(args):
    subprocess.run(["git", "status"])


# git@github.com-rbdannenberg:rbdannenberg/pm_csharp.git
# git@github.com-rbdannenberg:PortMidi/pm_csharp.git
# git push --set-upstream origin main

def newrepo(args):
    print("- you will need a URL like " +
          "git@github.com-rbdannenberg:PortMidi/pm_csharp.git")
    if not confirm("create local repo and initial check in"):
        print("- vc new command exited without any changes.")
        return
    subprocess.run(["git", "init"])
    # rename master to main -- less offensive, more compatible with github
    subprocess.run(["git", "checkout", "-b", "main"])
    local_push()
    url = input("URL for remote repository (you may need a URL in the\n" +
                "    form git@github.com-<userid>:<userid>/<repo>.git: ")
    subprocess.run(["git", "remote", "add", "origin", url])
    subprocess.run(["git", "fetch", "--all"])
    subprocess.run(["git", "branch", "--set-upstream-to=origin/main", "main"])
    # in case there are files already, e.g. license or README.md, pull them in
    pull([], extra_pull_args=["--allow-unrelated-histories"])
    if not os.path.isfile("README.md"):
        if confirm("create README.md (optional)"):
            with open("README.md", "w") as readme:
                readme.write("# " + url)
            subprocess.run(["git", "add", "README.md"])
            subprocess.run(["git", "commit", "-m", "created README.md"])
    # subprocess.run(["git", "branch", "-M", "main"])
    push(["push"], extra_push_args=["--set-upstream", "origin", "main"])


def checkout(args):
    """args are ['checkout', <repo url>, <local directory>, <branch>]"""
    if len(args) < 2:
        show_help()
        print('COMMAND ERROR: no URL given after "checkout"')
        exit()
    elif len(args) < 3:
        url = urlparse(args[1])
        path = url[2]
        dir = os.path.split(path)
        print("- found path components:", dir)
        # get after "/" and before ".":
        #     git@github.com:rbdannenberg/soundcool.git -> soundcool
        dir = dir[-1].split(".")[0]
        print("- derived '" + dir + "' as local directory")
        if os.path.exists(dir):
            print("-", dir, "already exists, checkout cancelled")
            return
        inp = input("Type Y to proceed: ")
        if inp != "Y":
            print("- user cancelled checkout")
            return
    else:
        dir = args[2]
    if os.path.isdir(dir):
        raise Exception("Directory already exists: " + dir)
    if len(args) == 4:
        sp = subprocess.run(["git", "clone", "-b", args[3], args[1], dir],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        sp = subprocess.run(["git", "clone", args[1], dir],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = sp.stdout.decode("utf-8")
    print(out)
    out = sp.stderr.decode("utf-8")
    print(out)
    if out.find("Could not resolve hostname") >= 0:
        print("- Check status of Internet access")


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
