class User:
    def __init__(self, email, age):
        self.email = email   # should tag the user based on email
        self.age = age       # will be untagged at assignment time
        self.name = "Alice"  # untagged attribute


u = User("alice@example.com", 42)

print("AGE:", u.age)

new_age = u.age + 1
u.age= new_age+1
print("NEW AGE:", u.age)
print("name:", u.name)
