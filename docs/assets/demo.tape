Output docs/assets/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 760
Set Padding 24
Set TypingSpeed 25ms
Set Theme { "name": "Catppuccin Mocha", "background": "#11111b", "black": "#45475a", "brightBlack": "#585b70", "red": "#f38ba8", "brightRed": "#f38ba8", "green": "#a6e3a1", "brightGreen": "#a6e3a1", "yellow": "#f9e2af", "brightYellow": "#f9e2af", "blue": "#89b4fa", "brightBlue": "#89b4fa", "magenta": "#f5c2e7", "brightMagenta": "#f5c2e7", "cyan": "#94e2d5", "brightCyan": "#94e2d5", "white": "#bac2de", "brightWhite": "#a6adc8" }

Hide
Type "source .venv/bin/activate"
Enter
Type "clear"
Enter
Show
Type "homelab investigate jellyfin --inventory docs/assets/demo-incident.inventory.yaml --no-discover --no-history"
Enter
Sleep 8s
