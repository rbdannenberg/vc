# vc
vc - version control. A wrapper to avoid git exposure and damage.
This is the 10-foot pole with which I'm happy to touch git.

## Introduction
The interface presented by git is the worst thing I have seen since
IBM's JCL (Job Control Language). git's own documentation is full of
self-referential definitions and incomplete specifications, and the
web is full of wrong answers for every question about using git.

git is also too complicated for normal use. In trying to be
"complete" by supporting almoost anything conceivable, there are
pitfalls at every command.

This wrapper offers a simple model of git usage and a simple set of
commands. Some of these commands took hours of experimentation just
to figure out how to implement them in git. Thus, this implementation
stores "institutional knowledge" about git.

The model is simple: You have a local working directory and a remote
repo(sitory). You make changes to the working directory and run
`vc push` to push changes to the remote repo. There is a local repo,
but using it is discouraged. (You can run `vc push local` to push
changes to the local repo only, but this avoids sharing changes with
other developers and loses the safety of saving changes on the server,
both of which seem to be bad policies encouraged by git.)

You can update the working directory with changes from the remote repo
with `vc pull` at any time. If there are conflicts, 

At the beginning, either you have non-version-controlled software
locally that you wish to move to git (use `vc new` to get started),
or you have a repo and wish to copy sources to a local working
directory (use `vc checkout`).


## Install
Assuming you clone the repo to ~/vc and your shell install aliases on startup:

    alias vc='python3 ~/vc/vc.py'


## Command Summary

<pre>
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
</pre>
