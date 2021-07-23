@rem vc script for Windows
@echo off
rem
rem Roger B. Dannenberg
rem July 2021
rem
rem Open System Properties, click Environment Variables ..., and add this
rem directory (C:/?/?/?/vc) to the PATH variable.
rem
rem Then, to use vc, simply type "vc <args>" in a GUI CMD window.
rem
py vc.py %*
