# Provenance test covering all cases

class User:
    def __init__(self, email, age, nationality, income):
        self.email = email            
        self.age = age
        self.nationality = nationality
        self.income = income          # sensitive but not used in tests


# --- Setup two users ---
u  = User("alice@example.com", 30, 'USA', 600.5)
u2 = User("bob@example.com",   25, 'Canada', 600.0)


def helper(email):
    email = email + '  --- '
    print("Helper email:", email)

# --- Direct attribute reads ---
print("Alice email:", u.email)             
print("Alice age:", u.age)                  
print("Alice nationality:", u.nationality)  
helper(u.email)




# --- Derived from sensitive data ---
derived = u.email + " -- verified"    
print("Alice email modified:", derived)


# --- Clean data ---
num = 70
print("This variable is clean shouldn't be tainted:", num)


# --- Modify attribute to clean value ---
u.age = 999                           
print("Alice age modified:", u.age)               


# --- Multiple owner propagation ---
alice = u.age                          
bob   = u2.age                         

combined = alice + bob                 
print("Alice and Bob ages combined:", combined)           

print("Bob age:", u2.age)

# --- Arithmetic propagation across multiple ops ---
u2.nationality = u.nationality
print("Bob nationality:", u2.nationality)

income_diff = u2.income - u.income
print("Income difference:", income_diff)

bob_income_sum = u2.income + 1000
print("Bob income plus 1000:", bob_income_sum)

bob_income_like_alice = u2.income +0.5
print("Bob income plus 0.5:", bob_income_like_alice)

x = u2.age + 5                                            
print("Bob age modified:", x)


combined2 = combined + 5
print("Combined modified ages:", combined2)



