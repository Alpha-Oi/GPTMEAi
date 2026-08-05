import os

print("GPTMemory AI — Memory Manager")

print("1 — Scan chats")
print("2 — Parse chats")
print("3 — Build knowledge graph")

choice = input("Select: ")

if choice == "1":

    os.system("python memory/chat_loader.py")

elif choice == "2":

    os.system("python memory/chat_parser.py")

elif choice == "3":

    os.system("python memory/knowledge_builder.py")

else:

    print("Unknown command")