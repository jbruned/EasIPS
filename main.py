from easips import EasIPS
from sys import argv

# Instantiate EasIPS and run it, using the specified listen address
EasIPS().run(argv[1] if len(argv) > 1 else "127.0.0.1:9000")
