import os, sys
SQ = chr(39)
NL = chr(10)
base = os.path.join(chr(67)+chr(58), os.sep, chr(85)+'sers', 'kerpu', '.vscode', 'dictateme', 'app', 'src')
mono = SQ+'JetBrains Mono'+SQ+', '+SQ+'SF Mono'+SQ+', '+SQ+'Cascadia Code'+SQ+', '+SQ+'Fira Code'+SQ+', Consolas, monospace'
sans = SQ+'Outfit'+SQ+', -apple-system, BlinkMacSystemFont, '+SQ+'Segoe UI'+SQ+', Roboto, Oxygen, Ubuntu, Cantarell, '+SQ+'Helvetica Neue'+SQ+', sans-serif'
noise = 'data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27200%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%270.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27/%3E%3C/svg%3E'
ee = SQ+SQ

c = ''
def a(s): global c; c += s + NL

print('Building index.html...')
