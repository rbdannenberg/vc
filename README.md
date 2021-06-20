# vc
vc - version control. A wrapper to avoid git exposure and damage.
I never want to use git again.

## INSTALL
Assuming you clone the repo to ~/vc and your shell install aliases on startup:

    alias vc='python3 ~/vc/vc.py'


## COMMAND SUMMARY

<pre>
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
vc push local
    Just like "vc push" except this checks in (git commit) 
        to local repo only.
vc pull
    Check out (git pull) from the master repo.
vc info
    Get info about the repo.
vc new
    Given a local directory and a newly created remote repo, create a local
        repo and populate the remote repo from local files.
vc help
    Print this help.
</pre>
