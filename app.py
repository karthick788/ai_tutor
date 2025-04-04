from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from flask_wtf.csrf import CSRFProtect

from model import LearningModel
import os
import json

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this in production
csrf = CSRFProtect(app)
# Initialize learning model
model = LearningModel()
# In your Flask app initialization (usually where you create your app)
app.config['WTF_CSRF_ENABLED'] = False

@app.route("/")
def home():
    if "email" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@csrf.exempt  # This disables CSRF protection for this route only
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Basic validation
        if not email or not password:
            flash("Please fill in all fields", "danger")
            return redirect(url_for("login"))

        user = model.get_user(email)
        
        # In production, use password hashing like:
        # if user and check_password_hash(user["password"], password):
        if user and user["password"] == password:
            session["email"] = email
            session["name"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "danger")
            # Consider logging failed attempts in production

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
@csrf.exempt  # This disables CSRF for this specific route
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        if model.get_user(email):
            flash("Email already registered", "danger")
            return redirect(url_for("signup"))

        new_user = {
            "name": name,
            "email": email,
            "password": password,  # Note: In production, you should hash passwords
            "courses_enrolled": [],
            "topics_weak": [],
            "course_levels": {},
            "progress": {},
        }

        model.users.append(new_user)
        model.save_users()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/dashboard")
def dashboard():
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    # Pass the model to the template
    return render_template("dashboard.html", user=user, model=model)  # Add this line


@app.route("/courses")
def courses():
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    # Get all courses from your model
    courses = model.courses  # Or however you're storing courses

    return render_template("courses.html", courses=courses, user=user)


@app.route("/enroll-course/<course_name>", methods=["POST"])
@csrf.exempt  # Keep this if you're still skipping CSRF
def enroll_course(course_name):
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    # Check if already enrolled
    if course_name in user.get('courses_enrolled', []):
        flash(f"You're already enrolled in {course_name}!", "info")
        return redirect(url_for("course_detail", course_name=course_name))

    # Enroll the user
    if model.enroll_user_in_course(user['email'], course_name):
        flash(f"Successfully enrolled in {course_name}!", "success")
    else:
        flash("Enrollment failed", "danger")

    return redirect(url_for("course_detail", course_name=course_name))
@app.route("/course/<course_name>")
def course_detail(course_name):
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    # Find the course
    course = next(
        (c for c in model.courses if c["name"].lower() == course_name.lower()), None
    )
    if not course:
        flash("Course not found", "danger")
        return redirect(url_for("courses"))

    # Check if user needs to take pre-assessment
    needs_assessment = course_name.lower() not in [
        k.lower() for k in user.get("course_levels", {}).keys()
    ]

    # Get recommended modules
    recommended = model.recommend_modules(course_name, session["email"])

    return render_template(
        "course_detail.html",
        course=course,
        user=user,  # Pass user to template
        needs_assessment=needs_assessment,
        recommended=recommended,
    )


@app.route("/pre-assessment/<course_name>", methods=["GET", "POST"])
def pre_assessment(course_name):
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            # Retrieve the questions from session instead of generating new ones
            questions = session.get('assessment_questions', [])
            if not questions:
                raise ValueError("Assessment questions not found in session")
            
            answers = {}
            total_questions = len(questions)
            
            for i in range(1, total_questions + 1):
                answer_key = f"q{i}"
                answer = request.form.get(answer_key, "").strip().lower()
                if not answer:
                    flash(f"Please answer question {i}", "warning")
                    raise ValueError(f"Missing answer for question {i}")
                answers[answer_key] = answer

            # Calculate results using the same questions that were shown
            score = 0
            weak_topics = {}
            question_analysis = []
            
            for i, question in enumerate(questions, start=1):
                user_answer = answers.get(f'q{i}')
                correct_answer = question['correct_answer'].lower()
                is_correct = user_answer == correct_answer
                
                if is_correct:
                    score += 1
                else:
                    topic = question.get('topic', 'General')
                    weak_topics[topic] = weak_topics.get(topic, 0) + 1
                
                question_analysis.append({
                    'number': i,
                    'question': question['question'],
                    'user_answer': user_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct,
                    'topic': question.get('topic', 'General')
                })

        # Rest of your evaluation code remains the same...

            # Determine level
            percentage = score / total_questions
            if percentage >= 0.8:
                new_level = "Advanced"
            elif percentage >= 0.5:
                new_level = "Intermediate"
            else:
                new_level = "Beginner"

            # Update user data
            try:
                user_data = {
                    'course_levels': {**user.get('course_levels', {}), course_name: new_level.lower()},
                    'progress': user.get('progress', {})
                }
                
                if course_name not in user_data['progress']:
                    user_data['progress'][course_name] = {
                        'completed_modules': [],
                        'scores': [],
                        'weak_topics': []
                    }
                
                user_data['progress'][course_name]['scores'].append(score)
                
                current_weak_topics = list(weak_topics.keys())
                existing_weak_topics = user_data['progress'][course_name]['weak_topics']
                user_data['progress'][course_name]['weak_topics'] = list(set(existing_weak_topics + current_weak_topics))
                
                global_weak_topics = user.get('topics_weak', [])
                user_data['topics_weak'] = list(set(global_weak_topics + current_weak_topics))
                
                model.update_user(user['email'], user_data)
                
            except Exception as e:
                app.logger.error(f"Failed to update user data: {str(e)}")
                flash("Your results were saved but there was an issue updating your profile", "warning")

            result = {
                'score': score,
                'total': total_questions,
                'weak_topics': weak_topics,
                'new_level': new_level,
                'question_analysis': question_analysis,
                'percentage': int(percentage * 100)
            }
            
            return render_template(
                "assessment_result.html",
                course_name=course_name,
                result=result,
                is_pre_assessment=True,
            )
            
        except Exception as e:
            flash(f"Error processing assessment: {str(e)}", "danger")
            app.logger.error(f"Assessment error: {str(e)}")
            questions = model.generate_pre_assessment(course_name, user["email"])
            return render_template(
                "pre_assessment.html",
                course_name=course_name,
                questions=questions,
                total_questions=len(questions),
            )

    # GET request - show assessment form
    # GET request - show assessment form
    questions = model.generate_pre_assessment(course_name, user["email"])
    # Store questions in session for later validation
    session['assessment_questions'] = questions
    return render_template(
        "pre_assessment.html",
        course_name=course_name,
        questions=questions,
        total_questions=len(questions),
    )
def determine_level(self, percentage):
    if percentage >= 0.8:
        return "Advanced"
    elif percentage >= 0.5:
        return "Intermediate"
    return "Beginner"
@app.route("/assessment-result")
def assessment_result():
    if 'assessment_result' not in session:
        flash("No assessment results found", "danger")
        return redirect(url_for("courses"))  # Or wherever makes sense
        
    data = session.pop('assessment_result')
    return render_template(
        "assessment_result.html",
        course_name=data['course_name'],
        result=data['result'],
        is_pre_assessment=data['is_pre_assessment']
    )
@app.route("/module/<course_name>/<module_title>")
def view_module(course_name, module_title):
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    module = model.get_course_module(course_name, module_title)
    if not module:
        flash("Module not found", "danger")
        return redirect(url_for("course_detail", course_name=course_name))

    return render_template("module_detail.html", course_name=course_name, module=module,user=user)
@app.route("/module-assessment/<course_name>/<module_title>", methods=["GET", "POST"])
def module_assessment(course_name, module_title):
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    module = model.get_course_module(course_name, module_title)
    if not module:
        flash("Module not found", "danger")
        return redirect(url_for("course_detail", course_name=course_name))

    if request.method == "POST":
        try:
            # Collect all answers (q_1, q_2, etc.)
            answers = {}
            total_questions = len(module['assessment'])
            
            for i in range(1, total_questions + 1):
                answer_key = f"q_{i}"
                answer = request.form.get(answer_key)
                if not answer:
                    flash(f"Please answer question {i}", "warning")
                    return redirect(url_for("module_assessment", 
                                          course_name=course_name, 
                                          module_title=module_title))
                answers[answer_key] = answer

            # Evaluate answers
            result = model.evaluate_module_assessment(
                course_name, module_title, session["email"], answers
            )

            return render_template(
                "assessment_result.html",
                course_name=course_name,
                module_title=module_title,
                result=result,
                is_pre_assessment=False,
            )
            
        except Exception as e:
            flash(f"Error processing assessment: {str(e)}", "danger")
            app.logger.error(f"Assessment error: {str(e)}")
            return redirect(url_for("module_assessment", 
                                  course_name=course_name, 
                                  module_title=module_title))

    # GET request - show assessment form
    return render_template(
        "module_assessment.html",
        course_name=course_name,
        module_title=module_title,
        questions=module["assessment"],
        total_questions=len(module["assessment"])
    )
@app.route("/test-result")
def test_result():
    test_result = {
        'score': 8,
        'total': 10,
        'weak_topics': ['algebra', 'geometry'],
        'new_level': 'intermediate'
    }
    return render_template(
        "assessment_result.html",
        course_name="Test Course",
        result=test_result,
        is_pre_assessment=True,
    )




@app.route("/progress")
def progress():
    if "email" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    user = model.get_user(session["email"])
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("login"))

    # Calculate basic progress metrics
    progress_data = {
        'enrolled_courses': len(user.get('courses_enrolled', [])),
        'completed_modules': sum(
            len(course.get('completed_modules', [])) 
            for course in user.get('progress', {}).values()
        ),
        'weak_topics': len(user.get('topics_weak', []))
    }

    return render_template("progress.html", user=user, progress=progress_data)
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
