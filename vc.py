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
         main repo.
    Always checks in files that have changed (as in git commit -a)
    Prompts for what to do with files that are not managed. 
    Responses to prompts are:
         a - add to repo
         i - add file to ignore list
         x - add file's extension to the ignore list
         d - delete the file (after confirm)
         p - pass (do not add to repo, do nothing with file)
         p n - pass on everything in directory n, e.g. if prompt is
             a/b/c.h, '2' will pass on everything in a/b
         ? or h - print this help and prompt again
         1,2,3,... - add nth folder of this path to ignore list;
             if prompt is xyz/tmp/foo.test, '2' will add /xyz/tmp/
             to .gitignore.
    FOR BRANCHES
    If the current branch is not main, merge main with the branch
    If there is a conflict, stop so user can resolve conflicts
        (see vc resolve)
    Recommit the branch
    Push to the branch to remote
    
vc push local
    Just like "vc push" except this checks in (git commit) 
        to local repo only.
vc pull
    Check out (git pull) from the main repo.

vc reset
    Force local repo to match main repo

vc resolve
    If there is a merge conflict, you must manually fix the files to resolve
    conflicts. Then use "vc resolve" to push the changes to the repo. If you
    are on a branch, the changes will be pushed to the corresponding remote
    branch.

vc rm <file>
    Remove <file> from local repo and from local filesystem. Use push to
    update the main repo.

Note: I don't want to encourage branches, but the basics are:
git branch new-branch-name -- create a new branch, do not change working branch
git checkout new-branch-name -- make new-branch-name the working branch
git checkout main -- return to main as the working branch
git merge new-branch-name -- merge new-branch-name changes into working branch

But AMADS project is using branches and pull requests, so the following
are implemented to support the project conventions:

vc mkbranch <branch-name>
    Create a new branch named <branch-name>. Warns if branch-name exists.

vc branch
    Select a branch and make it current

(see vc push for special branch behavior)
"""

repo_root = None


def show_help():
    print(HELP)


def git_run(command, capture=False):
    """use subprocess to run a command. Print the command first. 
    If capture is False, use stdout and stderr.
    If capture is True, use PIPE for stdout and stderr
    If capture is "stdout_only", use PIPE only for stdout
    """
    print("* run: ", end="")
    for field in command:
        print(field + " ", end="")
    print()
    if capture == "stdout_only":
        sp = subprocess.run(command,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elif capture:
        sp = subprocess.run(command,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        sp = subprocess.run(command)
    return sp


def sp_stdout(sp):
    return sp.stdout.decode("utf-8")


def sp_stderr(sp):
    return sp.stderr.decode("utf-8")


def get_root(suffix):
    global repo_root
    if not repo_root:
        sp = git_run(["git", "rev-parse", "--show-toplevel"], "stdout_only")
        repo_root = sp_stdout(sp).strip()
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
        sp = git_run(["git", "remote", "-v"], True)
        remotes = sp_stdout(sp).splitlines()
        errout = sp_stderr(sp)
        if len(remotes) == 2 and remotes[0].find("origin") == 0:
            # expected in simple cases
            remote = remotes[0]
            loc2 = remote.find("(")
            if loc2 < 0:
                raise Exception("Could not make sense of remote: " + remote)
            print("- " + remote[7 : loc2])
        elif len(errout) > 0:
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
    sp = git_run(["git", "-c", "color.ui=false", "status"],
                 capture="stdout_only")
    # first line is main or branch name:
    branch = sp_stdout(sp).split('\n', 1)[0]
    print("- " + branch)
    return branch[10 : ].strip()  # strip "On branch " from beginning


def get_branches():
    """Get a list of branches with current one at the beginning"""
    sp = git_run(["git", "-c", "color.ui=false", "branch"],
                 capture = "stdout_only")
    # output is lines with branch names. current branch has "*"
    branches = [None]
    for b in sp_stdout(sp).split('\n'):
        b = b.strip()
        if len(b) > 0:
            if b[0] == "*":
                branches[0] = b[1 : ].strip()
            else:
                branches.append(b)
    print(branches)
    return branches


def warn_about_hash_files(src):
    """
    Copy a directory and its contents, handling files with hash (#) characters.
    """
    for root, dirs, files in os.walk(src):
        for file in files:
            if '#' in file:
                print("WARNING: Backup is skipping file with hash character:")
                print(f"    {os.path.join(root, file)}")
                print("Recommend to delete it.")
                delete_after_confirm(os.path.join(root, file))


def make_backup():
    backups = get_root("-backups")
    if not os.path.isdir(backups):
        if os.path.isfile(backups):
            raise Exception("Unexpected file: " + backups)
        os.mkdir(backups)
    backup = backups + "/" + time.strftime("%Y%m%d-%H%M%S")
    warn_about_hash_files(get_root(""))
    shutil.copytree(get_root(""), backup,
                    ignore=shutil.ignore_patterns('.vs', '.git', '*.vcxproj',
                               'CMakeFiles', 'CMakeScripts', 'Debug', '*#*',
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


def get_number(prompt, low, high):
    inp = input("Type number of " + prompt + " or anything else to ignore:" )
    try:
        i = int(inp)
    except ValueError:
        return False
    if i < low or i > high:
        return false
    return i


def delete_after_confirm(filepath):
    if confirm("delete " + filepath):
        try:
            if os.path.isfile(filepath) or os.path.islink(filepath):
                os.remove(filepath)
            elif os.path.isdir(filepath):
                shutil.rmtree(filepath)
            else:
                print(f"Could not delete {filepath}. Please do it manually.")
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
            print("... proceeding as if user said No to delete.")
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

    if file == "files_with_conflicts.txt":
        inp = "p"  # pass
    else:
        inp = input("  " + file + ": [aixdph123...] ")
    if inp == "a":
        git_run(["git", "add", get_root("/" + file)])
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
        file_to_delete = get_root("/" + file)
        if not delete_after_confirm(file_to_delete):
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
        # p <digit> handling:
        # create a list representing the path
        folders = []
        path = file  # make a copy
        while path != "":
            head, tail = os.path.split(path)
            folders.append(tail)
            path = head
        folders.reverse()
        # now file a/b/c.h becomes [a, b, c.h]
        # only allow selection of a folder on path
        if os.path.isfile(file):
            folders.pop()  # remove file as an option
        if len(folders) < inp:
            print("- there are not", inp, "folders on path, try again")
            handle_untracked_file(file)
            return
        # construct path where number of directories is given by <digit>:
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
        # folders is now a list of folder names maybe followed by a file
        inp = int(inp)
        # only allow selection of a folder on path:
        if os.path.isfile(file):
            folders.pop()  # remove file as an option
        if len(folders) < inp:
            print("- there are not", inp, "folders on path, try again")
            handle_untracked_file(file)
            return
        del folders[inp : ]  # remove folders beyond specified digit
        # rebuild the path to be ignored
        path = folders[0]
        for folder in folders[1:]:
            path = os.path.join(path, folder)
        pass_on_this_path = path + "/"  # we can skip some matching paths
        add_to_gitignore("/" + path + "/")
    elif os.path.isdir(file):
        print("it's a directory...")
        # it's a directory. Prompt for disposition of each file in the
        # dir tree:
        for (dirpath, dirnames, filenames) in os.walk(get_root("/" + file)):
            for name in filenames:
                handle_untracked_file(os.path.join(dirpath, name))
    else:
        print(UNMANAGED_RESPONSES)
        handle_untracked_file(file)
        

def local_push():
    sp = git_run(["git", "-c", "color.ui=false", "commit", "-a", 
                  "--dry-run", "-m", "dry run"], capture=True)
    dryrun = sp_stdout(sp)
    dryrunerr = sp_stderr(sp)
    untracked = find_untracked(dryrun + dryrunerr)
    if len(untracked) > 0:
        print("- found untracked files. Specify what to do:")
        for file in untracked:
            handle_untracked_file(file)
    git_run(["git", "commit", "-a"])
    print("- finished push to local repo")


def process_possible_merge_conflict(out):
    """look for Merge conflict in git output and deal with it.
    This can come from either merging main branch into another
    branch or doing a git pull before a git push. Writes
    new file files_with_conflicts.txt if there are conflicts.
    Returns True iff a conflict occurred and must be resolved.
    """
    if out.find("Merge conflict") >= 0:
        conflict_files = ""
        lines = out.splitlines()
        with open("files_with_conflicts.txt", "w") as text_file:
            for line in lines:
                pos = line.find("Merge conflict in ")
                if pos >= 0:
                    filename = line[pos + 18 : ]
                    print(filename, file=text_file)
                    conflict_files += filename + "\n"
        print("- Automatic merge failed, so you must now",
              "manually merge changes")
        print("-     from the remote repo with your local",
              "changes; then run")
        print("-     'vc resolve' to finally push your changes",
              "to the remote repo.")
        print("-     files to edit are:")
        print(conflict_files)
        return True
    return False


def push(args, extra_push_args = []):
    branch = show_branch()
    # allow either "vc push local" or just "vc push":
    if (len(args) == 2 and args[1] == "local") or len(args) == 1:
        make_backup()
        local_push()
    on_main_branch = branch in ["main", "master"]
    print("- " + ('' if on_main_branch else 'not') + " on main branch")
    # (main branch could have another name but should be "main"
    if len(args) == 1:  # only do this if non-local
        if not confirm("push to remote repo"):
            print("- local changes are not committed to remote repo")
            return 
        if not on_main_branch:  # merge in main in case it changed on remote
            print("- not on main branch, so updating main branch " +
                  "and merging first")
            branches = get_branches()
            if "main" in branches:
                main_branch = "main"
            elif "master" in branches:
                main_branch = "master"
            else:
                print('- Could not find "main" or "master" in branches')
                print('- Exiting command; did nothing')
                return
            print("- merging with main branch before pushing branch to remote")
            do_a_checkout(main_branch)
            do_a_pull()
            do_a_checkout(branch)
            sp = git_run(["git", "-c", "color.ui=false", "merge", main_branch],
                         capture="stdout_only")
            out = sp_stdout(sp)
            print("- git output:\n", out, "-----------------")
            if process_possible_merge_conflict(out):
                return
            # do another commit after merging main
            print("- commit any local changes from merge before " +
                  "pushing to remote")
            git_run(["git", "commit"])
            # finally push to remote:
            print("- push local changes to remote")
            git_run(["git", "push", "origin", branch])
            git_run(["git", "branch", "--set-upstream-to=origin/" + branch,
                     branch])
            print("- remote main and branch were merged into local files, and")
            print("- local files pushed to remote branch " + branch)
            return
        else:
            git_run(["git", "fetch"])
            sp = git_run(["git", "-c", "color.ui=false", "status", "-sb"],
                         capture="stdout_only")
            out = sp_stdout(sp)
            if out.find("behind") >= 0:
                print("- You must pull changes from the remote repo")
                print("-     before you can push any local changes")
                if confirm("pull from remote repo now"):
                    sp = git_run(["git", "-c", "color.ui=false", "pull"],
                                  "stdout_only")
                    out = sp_stdout(sp)
                    print("- git output:\n", out, "-----------------")
                    if process_possible_merge_conflict(out):
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
                else:
                    print("- local changes are not committed to remote repo")
                    return

            sp = git_run(["git", "-c", "color.ui=false", "push"] + \
                         extra_push_args, capture="stdout_only")
            out = sp_stdout(sp)            
            print("- git output:\n", out, "-----------------")
            if out.find("hint: Updates were rejected because the tip of " +
                        "your current branch is behind") >= 0:
                # push failed. Give some advice:
                print("- 'vc push' did not complete because your local repo")
                print("-     is not up-to-date.")
            elif out.find(" denied to ") >= 0:
                print("- If git(hub) is using the wrong account,",
                      "it may be because git")
                print("-     has not configured your .git/config",
                      "file properly. You can")
                print("-     specify the account to use for",
                      "authorization in the url, e.g.")
                print('-     in .git/config under [remote ',
                      '"origin"], instead of')
                print("-         url =",
                     "git@github.com:rbdannenberg/vc.git")
                print("-     use")
                print("-         url =",
                      "git@github.com-rbdannenberg:rbdannenberg/vc.git")
                print("-     You can make this change manually",
                      "with any text editor.")


def do_a_pull(extra_args = []):
    sp = git_run(["git", "-c", "color.ui=false", "pull"] + extra_args,
                 capture="stdout_only")
    out = sp_stdout(sp)
    print("- git output:\n", out, "-----------------")
    if out.find("signing failed") >= 0:
        print("- if git tried to use the wrong account or userid for this")
        print("-   project, edit the remote origini url in .git/config to")
        print("-   have the form git@github.com-<userid>:<userid>/<repo>.git")
        print("-   and try again.")
    elif out.find("You have unstaged changes.") >= 0:
        print("- Could not pull from the main repo because you have local")
        print("-   modifications. You should run 'vc push local' to save your")
        print("-   local modifications. Then run 'vc pull' again to merge")
        print("-   changes from the main repo into your local copy.")


def pull(args):
    """Implements the vc pull command"""
    current_branch = show_branch()
    do_a_pull()
    on_main_branch = current_branch in ["main", "master"]
    if not on_main_branch:  # merge from main
        print("- Attempting to merge in changes from main branch")
        branches = get_branches()
        main_branch = False
        for b in branches:
            if b in ["main", "master"]:
                main_branch = b
        if not b:
            print("- Error: could not identify main branch name.")
            print("-    (No branch named main or master.)")
            print("-    Returning without pulling or merging main branch.")
            return
        print("- Switch to local version of main branch")
        git_run(["git", "checkout", main_branch])
        print("- Pull updates to main branch.")
        git_run(["git", "pull", "origin", main_branch])
        print("- Switch back to branch " + current_branch)
        git_run(["git", "checkout", current_branch])
        print("- Merge main branch updates into " + current_branch)
        sp = git_run(["git", "merge", main_branch], "stdout_only")
        out = sp_stdout(sp)
        print("- git output:\n", out, "-----------------")
        process_possible_merge_conflict(out)
        print("- CHECK CAREFULLY - RESOLVING A MERGE FROM MAIN IS UNTESTED")


def resolve(args):
    """Implementation of vc resolve. Uses files_with_conflicts.txt"""
    branch = show_branch()
    with open("files_with_conflicts.txt", "r") as text_file:
        conflict_files = text_file.read()
    conflict_branch = conflict_files.pop(0)
    if branch != conflict_branch:
        print("- conflict branch is not current branch; " +
              "switching to conflict branch")
        do_a_checkout(conflict_branch)
        branch = show_branch()
        if branch != conflict_branch:
            print("- failed to switch to conflict branch, exiting command")
            return
    on_main_branch = branch in ["main", "master"]

    if confirm("that the following files with conflicts are\n" + \
               "resolved and you are ready to push changes to the repo.\n" + \
               conflict_files):
        conflict_files = conflict_files.splitlines()
        sp = git_run(["git", "-c", "color.ui=false", "add"] + conflict_files,
                     capture="stdout_only")
        out = sp_stdout(sp)
        print("- git output;\n", out, "----------------")
        sp = git_run(["git", "commit", "-a"], capture="stdout_only")
        out = sp_stdout(sp)
        print("- git output;\n", out, "----------------")
        
        if on_main_branch:
            sp = git_run(["git", "rebase", "--continue"], capture="stdout_only")
            out = sp_stdout(sp)
            print("- git output;\n", out, "----------------")
            sp = git_run(["git", "push"], capture="stdout_only")
            out = sp_stdout(sp)
            print("- git output;\n", out, "----------------")
            print("- files with conflicts that you resolved have been pushed " + \
                  "to the repo")
        else:
            sp = git_run(["git", "push", "origin", branch], "stdout_only")
            out = sp_stdout(sp)
            print("- git output;\n", out, "----------------")
        os.remove("files_with_conflicts.txt")
            

def showinfo(args):
    git_run(["git", "status"])


# git@github.com-rbdannenberg:rbdannenberg/pm_csharp.git
# git@github.com-rbdannenberg:PortMidi/pm_csharp.git
# git push --set-upstream origin main

def newrepo(args):
    print("- you will need a URL like " +
          "git@github.com-rbdannenberg:PortMidi/pm_csharp.git")
    if not confirm("create local repo and initial check in"):
        print("- vc new command exited without any changes.")
        return
    git_run(["git", "init"])
    # rename master to main -- less offensive, more compatible with github
    git_run(["git", "checkout", "-b", "main"])
    local_push()
    url = input("URL for remote repository (you may need a URL in the\n" +
                "    form git@github.com-<userid>:<userid>/<repo>.git: ")
    git_run(["git", "remote", "add", "origin", url])
    git_run(["git", "fetch", "--all"])
    git_run(["git", "branch", "--set-upstream-to=origin/main", "main"])
    # in case there are files already, e.g. license or README.md, pull them in
    do_a_pull([], extra_args=["--allow-unrelated-histories"])
    if not os.path.isfile("README.md"):
        if confirm("create README.md (optional)"):
            with open("README.md", "w") as readme:
                readme.write("# " + url)
            git_run(["git", "add", "README.md"])
            git_run(["git", "commit", "-m", "created README.md"])
    # git_run(["git", "branch", "-M", "main"])
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
        sp = git_run(["git", "clone", "-b", args[3], args[1], dir],
                     capture=True)
    else:
        sp = git_run(["git", "clone", args[1], dir], capture=True)
    out = sp_stdout(sp)
    errout = sp_stderr(sp)
    print(out)
    if len(errout) > 0:
        print("- Error output: " + errout)
    if out.find("Could not resolve hostname") >= 0:
        print("- Check status of Internet access")


def rename(args):
    if len(args) >= 3:
        if len(args) == 3:
            print("- rename " + args[1] + " to " + args[2])
        else:
            print("- move " + args[1:-1] + " to " + args[-1])
        git_run(["git"] + args)


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
    git_run(["git", "rm", filename])


def reset(args):
    if confirm("that you want to reset your local repo to the main repo\n" +
               "and DELETE any local versions that may have changed"):
        # git fetch --all
        # git reset --hard origin/main
        print("- git output;")
        git_run(["git", "fetch", "--all"])
        git_run(["git", "reset", "--hard", "origin/main"])
        print("----------------")
        print("- local repo should now match remote, local files NOT in the")
        print("  remotely tracked files are unaltered")

                            
def mkbranch(args):
    """Implements vc mkbranch <branch>"""
    if len(args) == 1:
        branch_name = input("File to remove: ")
    elif len(args) == 2:
        branch_name = args[1]
    else:
        print('- command syntax is "vc branch <branch-name>"')
        return
    branches = get_branches()
    if branch_name in branches:
        print('- ' + branch_name + ' already exists, ignoring command')
        return
    if confirm("create branch " + branch_name):
        git_run(["git", "checkout", "-b", branch_name])


def do_a_checkout(branch):
    git_run(["git", "checkout", branch])


def branch(args):
    """Implements vc branch command"""
    if len(args) != 1:
        print("WARNING: branch command ignoring args", args[1:])
    branches = get_branches()
    print("Select the branch you want to work in:")
    i = 0
    current_msg = " (current)"
    for b in branches:
        i = i + 1
        print("    " + str(i) + ": " + b + current_msg)
        current_msg = ""
    i = get_number("branch", 1, i)
    if i == False:
        print("Command ignored, current branch is", branches[0])
        return
    branch = branches[i - 1]
    do_a_checkout(branch)


COMMANDS = ["push", "pull", "info", "new", "mv", "checkout", "rm", 
            "resolve", "reset", "mkbranch", "branch"]
IMPLEMENTATIONS = [push, pull, showinfo, newrepo, rename, checkout, remove,
                   resolve, reset, mkbranch, branch]

main()
