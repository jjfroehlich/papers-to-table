#!/bin/bash

# ##############################################################################
# Install ####
# ##############################################################################

# make dir
mkdir -p D:/code/local/paper-table-agent

# go to
cd D:/code/local/paper-table-agent || exit

# ++++++++++++++++++++++++++++++++++++++++
# Install Git ###
# ++++++++++++++++++++++++++++++++++++++++

# Install Git
# https://git-scm.com/downloads/win

# Check if installed
git --version

# # update git install
# git update-git-for-windows

# Go to 
cd D:/code/local/paper-table-agent || exit

# Initialize Git
git init

# add all files to the repository’s staging area while respecting your .gitignore rules
git add .

# Set Identity for Only the Current Repository
# Set your email:
git config user.email "jonathan.froehlich@gmail.com"

# Set your name:
git config user.name "jjfroehlich"

# Check status
git status

# Commit the files that you've staged
git commit -m "Initial commit"

# Rename the default branch to main
git branch -M main

# MANUALLY
# Create a new private repository on GitHub "paper-table-agent"

# Add the URL for the remote repository where your local repository will be pushed
git remote add origin https://github.com/jjfroehlich/paper-table-agent.git

# Check the new remote
git remote -v

# push to GitHub
git push -u origin main
