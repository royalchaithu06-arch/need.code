from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("STUDYPILOT_DB", BASE_DIR / "studypilot.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "studypilot-local-demo-change-before-deploy")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", JSON_SORT_KEYS=False)

GRADE_OPTIONS = [f"Class {n}" for n in range(1, 13)] + ["Undergraduate"]

SUBJECTS_BY_STAGE = {
    "early_primary": ["Mathematics", "English", "EVS"],
    "upper_primary": ["Mathematics", "English", "EVS"],
    "middle_school": ["Mathematics", "English", "Science", "Computer Studies"],
    "secondary": ["Mathematics", "English", "Science", "Computer Studies"],
    "senior_secondary": ["Mathematics", "English", "Physics", "Chemistry", "Biology", "Computer Science"],
    "college": ["DSA Foundations", "Programming", "DBMS", "Mathematics"],
}

# Each topic has two curated starter questions. This makes the first assessment quick and explainable.
def q(topic: str, text: str, options: list[str], answer: int, explanation: str, importance: int = 4) -> dict[str, Any]:
    return {"topic": topic, "text": text, "options": options, "correct_index": answer, "explanation": explanation, "importance": importance}

QUESTION_SETS: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("early_primary", "Mathematics"): [
        q("Counting & Addition", "You have 2 apples and get 3 more. How many apples do you have?", ["4", "5", "6", "7"], 1, "2 + 3 = 5.", 5),
        q("Counting & Addition", "What is 6 + 2?", ["7", "8", "9", "6"], 1, "Adding two more to six gives eight.", 5),
        q("Shapes & Patterns", "Which shape has three sides?", ["Circle", "Square", "Triangle", "Rectangle"], 2, "A triangle has three sides.", 4),
        q("Shapes & Patterns", "What comes next: red, blue, red, blue, ___?", ["Green", "Red", "Yellow", "Black"], 1, "The pattern alternates red and blue.", 3),
        q("Subtraction", "What is 5 − 2?", ["2", "3", "4", "5"], 1, "Take two away from five to get three.", 4),
        q("Subtraction", "There are 7 birds. 1 flies away. How many remain?", ["5", "6", "7", "8"], 1, "7 − 1 = 6.", 3),
    ],
    ("early_primary", "English"): [
        q("Words & Meaning", "Which word names an animal?", ["Run", "Happy", "Cat", "Blue"], 2, "Cat is the name of an animal.", 5),
        q("Words & Meaning", "Which word means the opposite of hot?", ["Warm", "Cold", "Bright", "Fast"], 1, "Cold is the opposite of hot.", 4),
        q("Sentences", "Choose the sentence that starts correctly.", ["the sun is bright.", "The sun is bright.", "the Sun is bright", "The sun is bright"], 1, "A sentence begins with a capital letter and ends with punctuation.", 5),
        q("Sentences", "Which mark usually ends a question?", ["?", ".", ",", "!"], 0, "A question mark is used at the end of a direct question.", 4),
        q("Grammar Basics", "Which word is an action?", ["Jump", "Chair", "Green", "Table"], 0, "Jump is an action word (verb).", 3),
        q("Grammar Basics", "Choose the correct word: I ___ happy.", ["am", "are", "is", "be"], 0, "Use 'am' with 'I'.", 3),
    ],
    ("early_primary", "EVS"): [
        q("Living Things", "Which one is a living thing?", ["Rock", "Tree", "Chair", "Pencil"], 1, "A tree grows and needs water and air.", 5),
        q("Living Things", "Which part of a plant usually absorbs water?", ["Flower", "Leaf", "Root", "Fruit"], 2, "Roots absorb water from the soil.", 4),
        q("Healthy Habits", "When should you wash your hands?", ["Only on Sundays", "Before eating and after using the toilet", "Never", "Only at school"], 1, "Handwashing helps reduce the spread of germs.", 5),
        q("Healthy Habits", "Which is the healthiest everyday drink?", ["Clean water", "Soft drink", "Paint", "Perfume"], 0, "Safe clean water supports health.", 4),
        q("Our Environment", "Which bin action helps the environment?", ["Throwing litter anywhere", "Putting waste in a bin", "Burning plastic indoors", "Dumping waste in a river"], 1, "Using bins keeps shared spaces cleaner.", 3),
        q("Our Environment", "What do plants need to grow?", ["Sunlight and water", "Only plastic", "Only stones", "No air"], 0, "Plants need sunlight, water, air and suitable nutrients.", 3),
    ],
    ("upper_primary", "Mathematics"): [
        q("Multiplication & Division", "What is 7 × 6?", ["36", "40", "42", "48"], 2, "7 multiplied by 6 equals 42.", 5),
        q("Multiplication & Division", "What is 36 ÷ 4?", ["8", "9", "10", "12"], 1, "36 divided into four equal groups gives nine each.", 5),
        q("Fractions", "Which fraction is equal to one half?", ["2/3", "2/4", "3/4", "1/3"], 1, "2/4 simplifies to 1/2.", 4),
        q("Fractions", "What is one quarter of 20?", ["4", "5", "10", "15"], 1, "20 divided by 4 is 5.", 4),
        q("Geometry", "How many degrees are in a right angle?", ["45°", "60°", "90°", "180°"], 2, "A right angle measures 90 degrees.", 3),
        q("Geometry", "A rectangle is 5 cm long and 3 cm wide. What is its perimeter?", ["8 cm", "15 cm", "16 cm", "20 cm"], 2, "Perimeter = 2 × (5 + 3) = 16 cm.", 3),
    ],
    ("upper_primary", "English"): [
        q("Parts of Speech", "In 'The bright moon shines', which word is an adjective?", ["The", "bright", "moon", "shines"], 1, "Bright describes the moon, so it is an adjective.", 5),
        q("Parts of Speech", "Which word is a verb?", ["Carefully", "Beautiful", "Swim", "Garden"], 2, "Swim describes an action.", 4),
        q("Sentence Skills", "Choose the correctly punctuated sentence.", ["Where are you going.", "Where are you going?", "where are you going?", "Where are you going,"], 1, "A direct question begins with a capital and ends with a question mark.", 5),
        q("Sentence Skills", "Choose the correct form: She ___ to school every day.", ["go", "goes", "going", "gone"], 1, "With 'she' in the simple present, use 'goes'.", 4),
        q("Vocabulary", "Which word is closest in meaning to 'rapid'?", ["Slow", "Quick", "Quiet", "Weak"], 1, "Rapid means fast or quick.", 3),
        q("Vocabulary", "What is the opposite of 'ancient'?", ["Old", "Historic", "Modern", "Past"], 2, "Modern is the opposite of ancient.", 3),
    ],
    ("upper_primary", "EVS"): [
        q("Plants & Animals", "Which process helps plants make their own food?", ["Evaporation", "Photosynthesis", "Condensation", "Digestion"], 1, "Plants use light, water and carbon dioxide in photosynthesis.", 5),
        q("Plants & Animals", "Which animal is a herbivore?", ["Tiger", "Cow", "Eagle", "Wolf"], 1, "A cow mainly eats plants.", 4),
        q("Earth & Resources", "Which is a renewable resource?", ["Sunlight", "Coal", "Petrol", "Natural gas"], 0, "Sunlight is replenished naturally.", 5),
        q("Earth & Resources", "Which action can save water?", ["Leave taps running", "Fix leaking taps", "Wash one cup for an hour", "Pour clean water away"], 1, "Fixing leaks avoids unnecessary water loss.", 4),
        q("Health & Safety", "Which nutrient is important for building and repairing body tissue?", ["Protein", "Only sugar", "Only salt", "Water vapour"], 0, "Protein supports growth and tissue repair.", 3),
        q("Health & Safety", "Why should food be covered?", ["To attract insects", "To protect it from dust and germs", "To make it disappear", "It has no purpose"], 1, "Covering food reduces contamination.", 3),
    ],
    ("middle_school", "Mathematics"): [
        q("Fractions & Ratios", "What is 3/4 of 20?", ["10", "12", "15", "16"], 2, "20 × 3/4 = 15.", 5),
        q("Fractions & Ratios", "Simplify the ratio 12:18.", ["2:3", "3:2", "4:9", "6:9"], 0, "Divide both terms by their greatest common divisor, 6.", 4),
        q("Algebra", "Solve: x + 7 = 15.", ["6", "7", "8", "22"], 2, "Subtract 7 from both sides to get x = 8.", 5),
        q("Algebra", "Simplify 3a + 2a.", ["5", "5a", "6a", "a⁵"], 1, "Like terms combine: 3a + 2a = 5a.", 4),
        q("Geometry & Data", "The angles in a triangle add up to:", ["90°", "180°", "270°", "360°"], 1, "The interior angles of a triangle sum to 180 degrees.", 3),
        q("Geometry & Data", "What is the mean of 4, 6 and 8?", ["5", "6", "7", "8"], 1, "(4 + 6 + 8) ÷ 3 = 6.", 3),
    ],
    ("middle_school", "English"): [
        q("Grammar & Tenses", "Choose the correct sentence.", ["They was playing.", "They were playing.", "They is playing.", "They be playing."], 1, "The plural subject 'they' takes 'were' in the past continuous.", 5),
        q("Grammar & Tenses", "Choose the past tense of 'write'.", ["Writed", "Wrote", "Written", "Writing"], 1, "The simple past form is 'wrote'.", 4),
        q("Reading & Meaning", "If a character is 'reluctant', they are:", ["Eager", "Unwilling or hesitant", "Very noisy", "Certain"], 1, "Reluctant means hesitant or unwilling.", 5),
        q("Reading & Meaning", "A paragraph's main idea is its:", ["Central point", "Longest word", "Last punctuation mark", "Page number"], 0, "The main idea is the central point a paragraph communicates.", 4),
        q("Writing Skills", "Which word connects ideas to show contrast?", ["Because", "However", "Therefore", "Firstly"], 1, "However signals contrast.", 3),
        q("Writing Skills", "Choose the correct punctuation: 'What a surprise__'", ["?", ".", "!", ","], 2, "An exclamation mark shows strong emotion or surprise.", 3),
    ],
    ("middle_school", "Science"): [
        q("Matter & Materials", "What is the change from liquid water to water vapour called?", ["Freezing", "Condensation", "Evaporation", "Melting"], 2, "Evaporation changes liquid to gas.", 5),
        q("Matter & Materials", "Which particle has a negative electric charge?", ["Proton", "Neutron", "Electron", "Nucleus"], 2, "Electrons carry negative charge.", 4),
        q("Forces & Energy", "The SI unit of force is:", ["Watt", "Newton", "Joule", "Volt"], 1, "Force is measured in newtons.", 5),
        q("Forces & Energy", "Which form of energy is associated with moving objects?", ["Kinetic", "Chemical only", "Soundless", "Stored only"], 0, "Kinetic energy is energy of motion.", 4),
        q("Living Systems", "Which organ pumps blood around the body?", ["Lung", "Heart", "Stomach", "Kidney"], 1, "The heart pumps blood through the circulatory system.", 3),
        q("Living Systems", "Which gas do plants take in for photosynthesis?", ["Oxygen", "Carbon dioxide", "Helium", "Hydrogen"], 1, "Plants use carbon dioxide to make sugars during photosynthesis.", 3),
    ],
    ("middle_school", "Computer Studies"): [
        q("Digital Basics", "Which component performs most processing instructions?", ["CPU", "Monitor", "Keyboard", "Speaker"], 0, "The CPU executes instructions and coordinates processing.", 5),
        q("Digital Basics", "Which is an example of an input device?", ["Monitor", "Printer", "Keyboard", "Projector"], 2, "A keyboard sends input to the computer.", 4),
        q("Internet Safety", "What should you do with a suspicious link from an unknown sender?", ["Click it quickly", "Share your password", "Avoid opening and verify the sender", "Download every file"], 2, "Verify unexpected messages and do not open suspicious links.", 5),
        q("Internet Safety", "A strong password should generally be:", ["Your first name only", "Unique and hard to guess", "123456", "The same everywhere"], 1, "Long, unique passwords are harder to guess.", 4),
        q("Logic & Algorithms", "An algorithm is best described as:", ["A step-by-step procedure", "A computer screen", "A type of cable", "A random guess"], 0, "An algorithm is a defined sequence of steps to solve a problem.", 3),
        q("Logic & Algorithms", "Which flowchart shape usually represents a decision?", ["Oval", "Diamond", "Arrow only", "Circle only"], 1, "A diamond is commonly used for a decision branch.", 3),
    ],
    ("secondary", "Mathematics"): [
        q("Algebra", "Solve 2x − 5 = 9.", ["2", "5", "7", "12"], 2, "Add 5 then divide by 2: x = 7.", 5),
        q("Algebra", "Factor x² − 9.", ["(x − 3)(x + 3)", "(x − 9)(x + 1)", "(x − 3)²", "x(x − 9)"], 0, "This is a difference of squares.", 5),
        q("Geometry", "What is the slope of a horizontal line?", ["0", "1", "Undefined", "−1"], 0, "A horizontal line has no vertical change, so slope is zero.", 4),
        q("Geometry", "For a right triangle, Pythagoras' theorem states:", ["a + b = c", "a² + b² = c²", "ab = c²", "a² − b² = c"], 1, "The squares of the legs sum to the square of the hypotenuse.", 4),
        q("Statistics & Probability", "The median of 2, 4, 9 is:", ["2", "4", "5", "9"], 1, "The median is the middle value in ordered data.", 3),
        q("Statistics & Probability", "What is the probability of heads on a fair coin?", ["0", "1/4", "1/2", "1"], 2, "Two equally likely outcomes mean probability 1/2.", 3),
    ],
    ("secondary", "English"): [
        q("Grammar & Usage", "Choose the grammatically correct sentence.", ["Neither of them are ready.", "Neither of them is ready.", "Neither them is ready.", "Neither is them ready."], 1, "'Neither' is treated as singular in formal agreement here.", 5),
        q("Grammar & Usage", "Change to passive voice: 'The team completed the task.'", ["The task completed the team.", "The task was completed by the team.", "The task is completing the team.", "The team was completed by the task."], 1, "The object becomes the subject; use 'was completed'.", 4),
        q("Reading & Inference", "An inference is a conclusion based on:", ["Evidence and reasoning", "A random word", "Only the title", "Guessing without clues"], 0, "Readers combine text evidence with reasoning to infer.", 5),
        q("Reading & Inference", "The author's tone is the author's:", ["Attitude toward the subject", "Page size", "Font choice only", "Number of paragraphs"], 0, "Tone communicates the writer's attitude.", 4),
        q("Writing & Vocabulary", "Choose the closest synonym for 'concise'.", ["Brief", "Confusing", "Lengthy", "Angry"], 0, "Concise means brief while still clear.", 3),
        q("Writing & Vocabulary", "Which sentence uses a semicolon correctly?", ["I studied; because I had a test.", "The test was difficult; I stayed calm.", ";I stayed calm.", "I; studied for the test."], 1, "A semicolon can connect closely related independent clauses.", 3),
    ],
    ("secondary", "Science"): [
        q("Physics & Energy", "The SI unit of work is:", ["Newton", "Joule", "Watt", "Pascal"], 1, "Work and energy are measured in joules.", 5),
        q("Physics & Energy", "Which relationship is Ohm's law?", ["V = IR", "P = mV", "F = mv", "E = mc"], 0, "Voltage equals current multiplied by resistance.", 5),
        q("Chemistry & Matter", "The atomic number equals the number of:", ["Neutrons only", "Protons", "Protons plus neutrons", "Electron shells"], 1, "Atomic number is defined by proton count.", 4),
        q("Chemistry & Matter", "A solution with pH 3 is generally:", ["Acidic", "Neutral", "Basic", "Always pure water"], 0, "pH below 7 is acidic.", 4),
        q("Biology & Systems", "Which cell organelle releases usable energy through respiration?", ["Mitochondrion", "Cell wall", "Vacuole only", "Ribosome only"], 0, "Mitochondria are a major site of cellular respiration.", 3),
        q("Biology & Systems", "Genes are made of segments of:", ["DNA", "Starch", "Water", "Fat only"], 0, "Genes are DNA sequences carrying hereditary information.", 3),
    ],
    ("secondary", "Computer Studies"): [
        q("Programming Logic", "What is the purpose of a loop?", ["Repeat a block of instructions", "Delete the operating system", "Display only images", "Encrypt every file"], 0, "Loops repeat instructions while a condition or sequence requires it.", 5),
        q("Programming Logic", "In many languages, which operator checks equality?", ["=", "==", "=>", "!==="], 1, "Double equals checks equality in many common languages.", 4),
        q("Data & Networks", "Which protocol is commonly used to load secure websites?", ["HTTPS", "FTP only", "SMTP only", "JPEG"], 0, "HTTPS is HTTP protected with TLS encryption.", 5),
        q("Data & Networks", "Which is a database table row commonly called?", ["Record", "Pixel", "Loop", "Packet header"], 0, "A row represents one record in a relational table.", 4),
        q("Cyber Safety", "What does multi-factor authentication add?", ["A second verification factor", "A public password", "Fewer security checks", "Automatic public sharing"], 0, "MFA combines two or more types of verification.", 3),
        q("Cyber Safety", "Which is the safest response to a password-reset email you did not request?", ["Enter details from its link", "Verify via the official website/app", "Forward it to everyone", "Reply with your password"], 1, "Use official channels rather than unverified links.", 3),
    ],
    ("senior_secondary", "Mathematics"): [
        q("Functions & Algebra", "If f(x) = 2x + 3, what is f(4)?", ["8", "10", "11", "14"], 2, "f(4) = 2(4) + 3 = 11.", 5),
        q("Functions & Algebra", "The derivative of x² is:", ["x", "2x", "2", "x³"], 1, "Using the power rule, d(x²)/dx = 2x.", 5),
        q("Probability & Statistics", "A fair die is rolled. What is the probability of an even number?", ["1/6", "1/3", "1/2", "2/3"], 2, "There are three even outcomes out of six.", 4),
        q("Probability & Statistics", "The mean of 2, 4, 6 and 8 is:", ["4", "5", "6", "8"], 1, "Their sum is 20; dividing by 4 gives 5.", 4),
        q("Trigonometry", "sin 30° equals:", ["0", "1/2", "√3/2", "1"], 1, "The standard exact value of sin 30° is 1/2.", 3),
        q("Trigonometry", "The identity sin²θ + cos²θ equals:", ["0", "sin θ", "1", "2"], 2, "This is a fundamental trigonometric identity.", 3),
    ],
    ("senior_secondary", "English"): [
        q("Grammar & Editing", "Choose the correct form: 'By next June, she ___ here for five years.'", ["will work", "will have worked", "has work", "worked"], 1, "Future perfect describes completion up to a future point.", 5),
        q("Grammar & Editing", "Which is the correct reported speech for: He said, 'I am tired.'", ["He said he is tired.", "He said that he was tired.", "He said I was tired.", "He says that he tired."], 1, "Backshift commonly changes 'am' to 'was' in reported speech.", 4),
        q("Comprehension & Argument", "A counterargument is:", ["A reason against a claim", "The title of an essay", "A spelling mistake", "A summary of punctuation"], 0, "A counterargument presents an opposing view.", 5),
        q("Comprehension & Argument", "A claim is strongest when supported by:", ["Relevant evidence", "Repeated opinions only", "Long sentences", "A decorative heading"], 0, "Relevant evidence makes an argument more credible.", 4),
        q("Vocabulary & Style", "'Ambiguous' most nearly means:", ["Having more than one possible meaning", "Very loud", "Completely certain", "Short and simple"], 0, "Ambiguous means open to multiple interpretations.", 3),
        q("Vocabulary & Style", "Which phrase is most formal for an academic report?", ["A lot of stuff", "Numerous factors", "Loads of things", "Things and bits"], 1, "Numerous factors is more precise and formal.", 3),
    ],
    ("senior_secondary", "Physics"): [
        q("Motion & Mechanics", "Acceleration is the rate of change of:", ["Displacement", "Velocity", "Mass", "Force"], 1, "Acceleration is change in velocity per unit time.", 5),
        q("Motion & Mechanics", "For constant acceleration, which equation is standard?", ["v = u + at", "v = m/a", "F = P/t", "P = IV²"], 0, "The first equation of motion is v = u + at.", 5),
        q("Electricity & Waves", "Electrical power can be calculated as:", ["P = VI", "P = V/I only", "P = I/V", "P = IR"], 0, "Electrical power is voltage multiplied by current.", 4),
        q("Electricity & Waves", "Frequency is measured in:", ["Metres", "Hertz", "Joules", "Coulombs"], 1, "Frequency is measured in hertz (cycles per second).", 4),
        q("Energy & Thermodynamics", "The SI unit of heat energy is:", ["Joule", "Kelvin", "Watt per metre", "Ampere"], 0, "Heat is energy, measured in joules.", 3),
        q("Energy & Thermodynamics", "An ideal isolated system conserves:", ["Total energy", "Only temperature", "Only volume", "Only speed"], 0, "Energy is conserved in an isolated system.", 3),
    ],
    ("senior_secondary", "Chemistry"): [
        q("Atomic Structure", "The maximum number of electrons in the first shell is:", ["2", "8", "18", "32"], 0, "The first principal shell holds up to two electrons.", 5),
        q("Atomic Structure", "Isotopes have the same number of protons but different numbers of:", ["Neutrons", "Atomic numbers", "Protons", "Elements"], 0, "Isotopes are forms of the same element with different neutron counts.", 5),
        q("Chemical Bonding", "An ionic bond forms mainly through:", ["Transfer of electrons", "Sharing only of neutrons", "Splitting protons", "Mixing nuclei"], 0, "Ionic bonding involves electron transfer and electrostatic attraction.", 4),
        q("Chemical Bonding", "A covalent bond generally involves:", ["Sharing electron pairs", "Losing all protons", "Sharing neutrons", "Breaking every nucleus"], 0, "Covalent bonds form when atoms share electron pairs.", 4),
        q("Acids & Reactions", "At room temperature, a neutral aqueous solution has pH close to:", ["1", "4", "7", "12"], 2, "Neutral water is approximately pH 7 at 25°C.", 3),
        q("Acids & Reactions", "A catalyst generally changes reaction rate by:", ["Lowering activation energy", "Changing products into elements", "Increasing reactant mass", "Being consumed completely"], 0, "Catalysts provide an alternative pathway with lower activation energy.", 3),
    ],
    ("senior_secondary", "Biology"): [
        q("Cell Biology", "Which organelle is the main site of protein synthesis?", ["Ribosome", "Lysosome", "Vacuole", "Golgi vesicle only"], 0, "Ribosomes assemble amino acids into proteins.", 5),
        q("Cell Biology", "The cell membrane is primarily a:", ["Phospholipid bilayer with proteins", "Solid cellulose wall in all cells", "DNA sheet", "Protein-free sugar shell"], 0, "The membrane's fluid-mosaic structure contains lipids and proteins.", 5),
        q("Genetics", "DNA replication is described as:", ["Semi-conservative", "Completely random", "Protein-only", "Non-cellular"], 0, "Each new DNA molecule contains one original and one new strand.", 4),
        q("Genetics", "Which molecule carries amino acids to a ribosome during translation?", ["tRNA", "DNA polymerase", "Glucose", "Cellulose"], 0, "Transfer RNA delivers amino acids during protein synthesis.", 4),
        q("Ecology & Human Health", "Organisms that make their own food are called:", ["Producers", "Decomposers only", "Parasites only", "Consumers"], 0, "Producers, such as plants, convert energy into organic matter.", 3),
        q("Ecology & Human Health", "Vaccines primarily help the body develop:", ["Immune memory", "More bones", "Digestive enzymes only", "A higher body temperature permanently"], 0, "Vaccines train the immune system to recognize a pathogen.", 3),
    ],
    ("senior_secondary", "Computer Science"): [
        q("Python Fundamentals", "Which Python data type stores an ordered, mutable collection?", ["tuple", "list", "int", "bool"], 1, "Lists preserve order and can be modified.", 5),
        q("Python Fundamentals", "What does len([2, 4, 6]) return?", ["2", "3", "6", "12"], 1, "The list contains three elements.", 5),
        q("Algorithms & Data", "What is the typical time complexity of binary search on sorted data?", ["O(n²)", "O(n)", "O(log n)", "O(2ⁿ)"], 2, "Binary search halves the search interval repeatedly.", 4),
        q("Algorithms & Data", "Which structure follows LIFO?", ["Queue", "Stack", "Graph", "Heap only"], 1, "A stack removes the last item added first.", 4),
        q("Data & Security", "Which SQL command retrieves rows?", ["SELECT", "DELETE", "DROP", "ALTER only"], 0, "SELECT queries data from a table.", 3),
        q("Data & Security", "Why should passwords be stored using a salted password hash?", ["To avoid storing the original password", "To make them public", "To reduce usernames", "To disable authentication"], 0, "A slow salted hash reduces the risk from database exposure.", 3),
    ],
    ("college", "DSA Foundations"): [
        q("Arrays", "What is the usual time complexity of accessing an array element by index?", ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 0, "Indexed array access is constant time.", 5),
        q("Arrays", "In a zero-indexed array of length 8, what is the last valid index?", ["8", "7", "6", "9"], 1, "Valid indexes run from 0 to n − 1.", 5),
        q("Searching & Sorting", "Binary search requires the data to be:", ["Stored only in a linked list", "Sorted", "All unique", "Reversed"], 1, "Binary search relies on sorted order.", 5),
        q("Searching & Sorting", "What is the typical average time complexity of merge sort?", ["O(n²)", "O(log n)", "O(n log n)", "O(1)"], 2, "Merge sort divides the list and merges on each level.", 4),
        q("Linked Lists", "A node in a basic singly linked list contains:", ["Only an index", "Data and a next reference", "Two queues", "A sort method"], 1, "A node stores data plus the reference to the next node.", 3),
        q("Stacks & Queues", "Which principle does a stack follow?", ["FIFO", "LIFO", "Random order", "Sorted order"], 1, "A stack follows last in, first out.", 4),
    ],
    ("college", "Programming"): [
        q("Core Concepts", "What is a function primarily used for?", ["Reusing a named block of code", "Storing only images", "Replacing all variables", "Turning off a program"], 0, "Functions package reusable behavior behind a name.", 5),
        q("Core Concepts", "Which construct repeats statements while a condition remains true?", ["if", "while loop", "class only", "import"], 1, "A while loop repeats while its condition evaluates to true.", 5),
        q("Data & Types", "Which data type represents true or false?", ["Boolean", "String", "Float", "Array index"], 0, "Boolean values represent truth values.", 4),
        q("Data & Types", "What is debugging?", ["Finding and fixing errors", "Deleting all code", "Writing only comments", "Installing a monitor"], 0, "Debugging is the process of locating and resolving defects.", 4),
        q("Logic & Testing", "Unit testing normally tests:", ["Small pieces of code in isolation", "An entire company", "Only the user manual", "Internet speed"], 0, "Unit tests focus on small units such as functions or methods.", 3),
        q("Logic & Testing", "What is an edge case?", ["An unusual boundary input or condition", "The project title", "A normal example only", "A syntax colour"], 0, "Edge cases test boundaries and unusual conditions.", 3),
    ],
    ("college", "DBMS"): [
        q("Relational Basics", "In a relational database, a primary key should uniquely identify:", ["A row", "A whole database server", "A CSS rule", "A network route"], 0, "A primary key uniquely identifies each record in a table.", 5),
        q("Relational Basics", "Which SQL command retrieves data?", ["SELECT", "INSERT only", "DROP", "GRANT only"], 0, "SELECT returns records from one or more tables.", 5),
        q("Normalization", "A common goal of normalization is to reduce:", ["Data redundancy", "Data accuracy", "Security checks", "All relationships"], 0, "Normalization organizes data to reduce unnecessary duplication.", 4),
        q("Normalization", "A foreign key usually references:", ["A key in another or the same table", "A CSS selector", "A password hash only", "A file extension"], 0, "Foreign keys represent relationships between records.", 4),
        q("Transactions", "In ACID, atomicity means a transaction is:", ["All-or-nothing", "Always slow", "Only read-only", "Never logged"], 0, "Atomicity prevents partial transaction completion.", 3),
        q("Transactions", "Which command normally makes a transaction's changes permanent?", ["COMMIT", "ROLLBACK", "SELECT", "EXPLAIN"], 0, "COMMIT saves the transaction's changes.", 3),
    ],
    ("college", "Mathematics"): [
        q("Functions & Algebra", "If f(x) = 2x + 3, what is f(4)?", ["8", "10", "11", "14"], 2, "2 × 4 + 3 = 11.", 5),
        q("Functions & Algebra", "The derivative of x² is:", ["x", "2x", "2", "x³"], 1, "The power rule gives 2x.", 5),
        q("Probability & Statistics", "The probability of rolling a 6 on a fair six-sided die is:", ["0", "1/6", "1/2", "1"], 1, "One of six equally likely outcomes is a 6.", 4),
        q("Probability & Statistics", "The mean of 3, 5 and 7 is:", ["4", "5", "6", "7"], 1, "(3 + 5 + 7) / 3 = 5.", 4),
        q("Discrete Mathematics", "A set with three distinct elements has how many subsets?", ["3", "6", "8", "9"], 2, "A set with n elements has 2ⁿ subsets, so 2³ = 8.", 3),
        q("Discrete Mathematics", "In a simple undirected graph, an edge connects:", ["Two vertices", "Only two databases", "An array and a stack", "A function to a variable"], 0, "An edge connects vertices in a graph.", 3),
    ],
}


def stage_for_grade(grade: str) -> str:
    if grade == "Undergraduate": return "college"
    try: number = int(grade.replace("Class", "").strip())
    except ValueError: return "middle_school"
    if number <= 2: return "early_primary"
    if number <= 5: return "upper_primary"
    if number <= 8: return "middle_school"
    if number <= 10: return "secondary"
    return "senior_secondary"


def subject_options(grade: str) -> list[str]:
    return SUBJECTS_BY_STAGE[stage_for_grade(grade)]


def get_questions(grade: str, subject: str) -> list[dict[str, Any]]:
    bank = QUESTION_SETS.get((stage_for_grade(grade), subject))
    # Some subjects share a nearby curriculum band when a grade-specific subject is not separately listed.
    if not bank:
        available = subject_options(grade)
        subject = subject if subject in available else available[0]
        bank = QUESTION_SETS.get((stage_for_grade(grade), subject), QUESTION_SETS[("middle_school", "Mathematics")])
    return [dict(item, id=index + 1, subject=subject) for index, item in enumerate(bank)]


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            grade TEXT NOT NULL DEFAULT 'Class 8',
            subject TEXT NOT NULL DEFAULT 'Science',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS student_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            grade TEXT NOT NULL,
            subject TEXT NOT NULL,
            attempt_type TEXT NOT NULL,
            focus_topic TEXT,
            total_score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            study_minutes INTEGER NOT NULL DEFAULT 30,
            topic_scores_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_attempts_user ON student_attempts(user_id, id DESC);
        """)
        demo = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@studypilot.app",)).fetchone()
        if not demo:
            conn.execute("INSERT INTO users (full_name,email,password_hash,grade,subject,created_at) VALUES (?,?,?,?,?,?)", (
                "Demo Student", "demo@studypilot.app", generate_password_hash("PilotDemo2026!"), "Class 8", "Science", datetime.now(timezone.utc).isoformat(timespec="seconds")
            ))


def now_local() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "name": row["full_name"], "email": row["email"], "grade": row["grade"], "subject": row["subject"]}


def current_user() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id: return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in to continue."}), 401
        return fn(*args, **kwargs)
    return wrapped


def read_topic_scores(conn: sqlite3.Connection, user_id: int, grade: str, subject: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute("SELECT topic_scores_json, attempt_type, created_at FROM student_attempts WHERE user_id=? AND grade=? AND subject=? ORDER BY id DESC LIMIT 20", (user_id, grade, subject)).fetchall()
    scores: dict[str, dict[str, Any]] = {}
    for row in rows:
        for item in json.loads(row["topic_scores_json"]):
            if item["topic"] not in scores:
                scores[item["topic"]] = {**item, "attempt_type": row["attempt_type"], "created_at": row["created_at"]}
    return scores


def make_plan(scores: dict[str, dict[str, Any]], grade: str, subject: str, minutes: int) -> list[dict[str, Any]]:
    bank = get_questions(grade, subject)
    topics: dict[str, int] = {}
    for item in bank: topics[item["topic"]] = item["importance"]
    candidates = []
    for topic, importance in topics.items():
        current = scores.get(topic)
        score = int(current["score"]) if current else 50
        priority = round((100 - score) * 0.8 + importance * 4, 1)
        if not current: label, action = "Baseline needed", "Take the quick diagnostic, then review the worked examples for this topic."
        elif score < 40: label, action = "Start here", "Relearn the core idea, study one worked example, then answer 3 guided questions."
        elif score < 70: label, action = "Build confidence", "Review the key rule and examples, then answer 5 practice questions without notes."
        else: label, action = "Maintain mastery", "Try mixed questions and schedule a short spaced review later."
        candidates.append({"topic": topic, "score": score if current else None, "importance": importance, "priority": priority, "priority_label": label, "action": action})
    candidates.sort(key=lambda x: (-x["priority"], x["topic"]))
    minutes = max(5, min(int(minutes or 30), 600))
    budget_slots = max(1, minutes // 5)  # Allocate in five-minute blocks so the plan never exceeds the budget.
    picked = candidates[:max(1, min(len(candidates), budget_slots))] if candidates else []
    if not picked: return []
    weights = [max(1.0, float(item["priority"])) for item in picked]
    extra_slots = budget_slots - len(picked)
    weight_sum = sum(weights)
    raw_extras = [extra_slots * weight / weight_sum for weight in weights]
    extras = [int(value) for value in raw_extras]
    leftovers = extra_slots - sum(extras)
    remainders = sorted(range(len(picked)), key=lambda i: raw_extras[i] - extras[i], reverse=True)
    for i in remainders[:leftovers]: extras[i] += 1
    allocations = [(1 + value) * 5 for value in extras]
    return [{**item, "minutes": allocations[i], "order": i + 1} for i, item in enumerate(picked)]


def dashboard_data(user: sqlite3.Row) -> dict[str, Any]:
    with get_db() as conn:
        scores = read_topic_scores(conn, user["id"], user["grade"], user["subject"])
        attempts = conn.execute("SELECT id,attempt_type,focus_topic,total_score,total_questions,study_minutes,created_at,grade,subject FROM student_attempts WHERE user_id=? ORDER BY id DESC LIMIT 8", (user["id"],)).fetchall()
        total_attempts = conn.execute("SELECT COUNT(*) AS c FROM student_attempts WHERE user_id=?", (user["id"],)).fetchone()["c"]
    bank = get_questions(user["grade"], user["subject"])
    topic_scores = []
    topics: dict[str, int] = {}
    for item in bank: topics[item["topic"]] = item["importance"]
    for topic, importance in topics.items():
        score = scores.get(topic)
        topic_scores.append({"topic": topic, "importance": importance, "score": score["score"] if score else None, "correct": score["correct"] if score else None, "total": score["total"] if score else None})
    assessed = [x["score"] for x in topic_scores if x["score"] is not None]
    average = round(sum(assessed) / len(assessed)) if assessed else None
    return {"user": public_user(user), "grade_options": GRADE_OPTIONS, "subjects": subject_options(user["grade"]), "topic_scores": topic_scores, "average_score": average, "topics_assessed": len(assessed), "total_topics": len(topic_scores), "total_attempts": total_attempts, "attempts": [dict(x) for x in attempts], "study_plan": make_plan(scores, user["grade"], user["subject"], 30)}


@app.get("/")
def home():
    return render_template("index.html", grade_options=GRADE_OPTIONS)

@app.get("/health")
def health(): return jsonify({"status": "ok", "app": "StudyPilot"})

@app.get("/api/me")
def api_me():
    user = current_user()
    return jsonify({"authenticated": bool(user), "user": public_user(user) if user else None, "grades": GRADE_OPTIONS, "demo_email": "demo@studypilot.app", "demo_password": "PilotDemo2026!"})

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:70]
    email = str(data.get("email", "")).strip().lower()[:160]
    password = str(data.get("password", ""))
    grade = str(data.get("grade", "Class 8"))
    subject = str(data.get("subject", "Science"))
    if len(name) < 2: return jsonify({"error": "Please enter your name."}), 400
    if "@" not in email or "." not in email.split("@")[-1]: return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 6: return jsonify({"error": "Use a password with at least 6 characters."}), 400
    if grade not in GRADE_OPTIONS: return jsonify({"error": "Choose a valid class or study level."}), 400
    if subject not in subject_options(grade): return jsonify({"error": "Choose a subject available for the selected class."}), 400
    try:
        with get_db() as conn:
            cur = conn.execute("INSERT INTO users (full_name,email,password_hash,grade,subject,created_at) VALUES (?,?,?,?,?,?)", (name,email,generate_password_hash(password),grade,subject,now_local()))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists. Please log in."}), 409
    session.clear(); session["user_id"] = user_id
    user = current_user()
    return jsonify({"ok": True, "user": public_user(user), "message": "Welcome to StudyPilot! Your profile is saved."})

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Email or password is incorrect."}), 401
    session.clear(); session["user_id"] = row["id"]
    return jsonify({"ok": True, "user": public_user(row), "message": "You're back. Let's keep the progress going."})

@app.post("/api/demo-login")
def api_demo_login():
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email=?", ("demo@studypilot.app",)).fetchone()
    if not row: return jsonify({"error": "Demo account is not available."}), 500
    session.clear(); session["user_id"] = row["id"]
    return jsonify({"ok": True, "message": "Demo workspace opened."})

@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.get("/api/subjects")
def api_subjects():
    grade = request.args.get("grade", "Class 8")
    if grade not in GRADE_OPTIONS: return jsonify({"error": "Invalid class."}), 400
    return jsonify({"grade": grade, "subjects": subject_options(grade)})

@app.post("/api/profile")
@login_required
def api_profile():
    data = request.get_json(silent=True) or {}
    grade = str(data.get("grade", "")); subject = str(data.get("subject", ""))
    if grade not in GRADE_OPTIONS: return jsonify({"error": "Choose a valid class or study level."}), 400
    if subject not in subject_options(grade): return jsonify({"error": "Choose a subject available for this class."}), 400
    with get_db() as conn:
        conn.execute("UPDATE users SET grade=?, subject=? WHERE id=?", (grade,subject,session["user_id"]))
    return jsonify({"ok": True, "user": public_user(current_user()), "message": "Your learning path has been updated."})

@app.get("/api/dashboard")
@login_required
def api_dashboard():
    user = current_user()
    return jsonify(dashboard_data(user))

@app.get("/api/questions")
@login_required
def api_questions():
    user = current_user()
    subject = str(request.args.get("subject") or user["subject"])
    mode = request.args.get("mode", "diagnostic")
    topic = str(request.args.get("topic", ""))
    if subject not in subject_options(user["grade"]): return jsonify({"error": "Select a subject available for your class."}), 400
    bank = get_questions(user["grade"], subject)
    if mode == "targeted": bank = [x for x in bank if x["topic"] == topic]
    if not bank: return jsonify({"error": "No questions were found for that topic."}), 404
    # Never send the answer key to the browser.
    return jsonify({"mode": mode, "subject": subject, "topic": topic or None, "questions": [{k:v for k,v in x.items() if k not in ("correct_index", "explanation", "importance")} for x in bank]})

@app.post("/api/submit")
@login_required
def api_submit():
    user = current_user()
    data = request.get_json(silent=True) or {}
    subject = str(data.get("subject") or user["subject"])
    mode = str(data.get("mode", "diagnostic"))
    topic = str(data.get("topic") or "")
    if subject not in subject_options(user["grade"]): return jsonify({"error": "Invalid subject."}), 400
    if mode not in ("diagnostic", "targeted"): return jsonify({"error": "Invalid quiz mode."}), 400
    try: minutes = max(5, min(int(data.get("study_minutes", 30)), 600))
    except (ValueError, TypeError): return jsonify({"error": "Study time must be a number."}), 400
    raw_answers = data.get("answers")
    if not isinstance(raw_answers, list) or not raw_answers: return jsonify({"error": "Answer the quiz before submitting."}), 400
    bank = get_questions(user["grade"], subject)
    if mode == "targeted": bank = [qitem for qitem in bank if qitem["topic"] == topic]
    by_id = {x["id"]: x for x in bank}
    submitted: dict[int,int] = {}
    for answer in raw_answers:
        try: qid, selected = int(answer["question_id"]), int(answer["selected_index"])
        except (KeyError,ValueError,TypeError): return jsonify({"error": "One of the submitted answers is invalid."}), 400
        if qid not in by_id: return jsonify({"error": "A question does not belong to this quiz. Reload and try again."}), 400
        if selected < 0 or selected >= len(by_id[qid]["options"]): return jsonify({"error": "Choose a valid option for every question."}), 400
        if qid in submitted: return jsonify({"error": "A question was submitted twice."}), 400
        submitted[qid] = selected
    if set(submitted) != {item["id"] for item in bank}:
        return jsonify({"error": "Please answer every question before submitting."}), 400
    previous: dict[str, dict[str, Any]]
    with get_db() as conn:
        previous = read_topic_scores(conn, user["id"], user["grade"], subject)
        correct_by_topic: dict[str,int] = {}; total_by_topic: dict[str,int] = {}; total_correct = 0
        for qid, selected in submitted.items():
            item = by_id[qid]; topic_name = item["topic"]
            correct = int(selected == item["correct_index"]); total_correct += correct
            correct_by_topic[topic_name] = correct_by_topic.get(topic_name,0) + correct
            total_by_topic[topic_name] = total_by_topic.get(topic_name,0) + 1
        topic_results = []
        for topic_name, total in total_by_topic.items():
            score = round(correct_by_topic[topic_name] * 100 / total)
            old = previous.get(topic_name, {}).get("score")
            topic_results.append({"topic":topic_name,"correct":correct_by_topic[topic_name],"total":total,"score":score,"change":score-old if old is not None else None})
        topic_results.sort(key=lambda x: x["score"])
        all_topics = []
        importance_map = {x["topic"]:x["importance"] for x in get_questions(user["grade"],subject)}
        for name, total in total_by_topic.items():
            all_topics.append({"topic":name,"correct":correct_by_topic[name],"total":total,"score":round(correct_by_topic[name]*100/total),"importance":importance_map.get(name,4)})
        cur = conn.execute("INSERT INTO student_attempts(user_id,grade,subject,attempt_type,focus_topic,total_score,total_questions,study_minutes,topic_scores_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (user["id"],user["grade"],subject,mode,topic or None,total_correct,len(submitted),minutes,json.dumps(all_topics),now_local()))
        attempt_id = cur.lastrowid
        fresh = read_topic_scores(conn,user["id"],user["grade"],subject)
    plan = make_plan(fresh,user["grade"],subject,minutes)
    return jsonify({"attempt_id":attempt_id,"mode":mode,"subject":subject,"topic":topic or None,"score":round(total_correct*100/len(submitted)),"correct":total_correct,"total":len(submitted),"topic_results":topic_results,"topic_scores":[{"topic":key,"score":val["score"],"correct":val["correct"],"total":val["total"]} for key,val in fresh.items()],"study_plan":plan,"recommendation":plan[0] if plan else None,"message":"Your plan is based on your latest topic scores."})

@app.get("/api/plan")
@login_required
def api_plan():
    user = current_user(); subject = request.args.get("subject",user["subject"])
    if subject not in subject_options(user["grade"]): return jsonify({"error":"Invalid subject."}),400
    try: minutes = max(5,min(int(request.args.get("minutes","30")),600))
    except (ValueError,TypeError): return jsonify({"error":"Enter a valid study duration."}),400
    with get_db() as conn: scores = read_topic_scores(conn,user["id"],user["grade"],subject)
    return jsonify({"minutes":minutes,"study_plan":make_plan(scores,user["grade"],subject,minutes)})

@app.get("/api/history")
@login_required
def api_history():
    user = current_user()
    with get_db() as conn:
        rows = conn.execute("SELECT id,attempt_type,focus_topic,total_score,total_questions,study_minutes,created_at,grade,subject,ROUND(100.0*total_score/total_questions) score_percent FROM student_attempts WHERE user_id=? ORDER BY id DESC LIMIT 30",(user["id"],)).fetchall()
    return jsonify({"attempts":[dict(x) for x in rows]})

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=os.environ.get("FLASK_DEBUG")=="1")
