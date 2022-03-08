from easips import EasIPS
from sys import argv
EasIPS().run(argv[1] if len(argv) > 1 else "127.0.0.1:9000")
