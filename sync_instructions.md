# 每天 00:00 自动同步 tianhe-aba skill 到 GitHub
this function is triggered at midnight by schedule tool
steps:
1. cd C:\Users\Dell\.qoder\skills\tianhe-aba
2. check branch is main (git branch --show-current)
3. git pull origin main
4. if files changed, git add . -> git commit -m "auto sync $(Get-Date -Format yyyy-MM-dd HH:mm)" -> git push origin main
5. echo sync complete