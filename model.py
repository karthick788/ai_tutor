import json
import os
import random
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class LearningModel:
    def __init__(self):
        self.users_file = os.path.join('data', 'users.json')
        self.courses_file = os.path.join('data', 'courses.json')
        self.question_bank_file = os.path.join('data', 'question_bank.json')
        self.load_data()
        self.vectorizer = TfidfVectorizer(stop_words='english')
        
    def load_data(self):
        with open(self.courses_file) as f:
            self.courses = json.load(f)['courses']
        
        with open(self.question_bank_file) as f:
            self.question_bank = json.load(f)['question_bank']
        
        with open(self.users_file) as f:
            self.users = json.load(f)
    
    def save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def get_user(self, email):
        for user in self.users:
            if user['email'] == email:
                return user
        return None
    
    def update_user(self, email, updates):
        for i, user in enumerate(self.users):
            if user['email'] == email:
                self.users[i].update(updates)
                break
        self.save_users()
    
    def generate_pre_assessment(self, course_name, user_email):
        user = self.get_user(user_email)
        if not user:
            return None
        
        # Get questions based on user's current level in this course
        course_level = user.get('course_levels', {}).get(course_name, 'beginner')  # Fixed typo: 'beginner' not 'beginner'
        
        # Filter questions for this course and difficulty level
        questions = []
        for topic in self.question_bank:
            if topic['topic'].lower() == course_name.lower():
                for q in topic['questions']:
                    if q['difficulty'].lower() == course_level.lower():
                        # Ensure each question has the required structure
                        formatted_question = {
                            'question': q['question'],
                            'options': q['options'],  # This should be a list of options
                            'answer': q['answer'],    # The correct answer
                            'difficulty': q['difficulty'],
                            'related_submodule': q.get('related_submodule', '')
                        }
                        questions.append(formatted_question)
        
        # Select 10 random questions if available
        assessment = random.sample(questions, min(10, len(questions))) if questions else []
        return assessment
    
    def evaluate_pre_assessment(self, course_name, user_email, answers):
        user = self.get_user(user_email)
        if not user:
            return None
        
        # Get correct answers from question bank
        correct_answers = {}
        for topic in self.question_bank:
            if topic['topic'].lower() == course_name.lower():
                for q in topic['questions']:
                    correct_answers[q['question']] = q['answer']
        
        # Calculate score and identify weak topics
        score = 0
        weak_topics = defaultdict(int)
        
        for question, user_answer in answers.items():
            if correct_answers.get(question) == user_answer:
                score += 1
            else:
                # Find the topic for this question
                for topic in self.question_bank:
                    if topic['topic'].lower() == course_name.lower():
                        for q in topic['questions']:
                            if q['question'] == question:
                                related_submodule = q.get('related_submodule', '').lower()
                                weak_topics[related_submodule] += 1
        
        # Determine new level based on score
        if score >= 8:
            new_level = 'advanced' if user.get('course_levels', {}).get(course_name) == 'intermediate' else 'intermediate'
        elif score >= 5:
            new_level = 'intermediate' if user.get('course_levels', {}).get(course_name) == 'beginner' else 'beginner'
        else:
            new_level = 'beginner'
        
        # Update user data
        updates = {
            'course_levels': {**user.get('course_levels', {}), course_name: new_level},
            'topics_weak': list(set(user.get('topics_weak', []) | set(weak_topics.keys()))),
            'progress': user.get('progress', {})
        }
        
        if course_name not in updates['progress']:
            updates['progress'][course_name] = {
                'completed_modules': [],
                'scores': [],
                'weak_topics': []
            }
        
        updates['progress'][course_name]['scores'].append(score)
        updates['progress'][course_name]['weak_topics'] = list(set(
            updates['progress'][course_name]['weak_topics'] + list(weak_topics.keys())
        ))
        
        self.update_user(user_email, updates)
        
        return {
            'score': score,
            'total': len(answers),
            'weak_topics': weak_topics,
            'new_level': new_level
        }
    
    def recommend_modules(self, course_name, user_email):
        user = self.get_user(user_email)
        if not user:
            return None
        
        # Get user's weak topics and current level
        weak_topics = user.get('progress', {}).get(course_name, {}).get('weak_topics', [])
        level = user.get('course_levels', {}).get(course_name, 'beginner')
        
        # Find matching modules
        recommended = []
        for course in self.courses:
            if course['name'].lower() == course_name.lower():
                for module in course['submodules']:
                    module_tags = [t.lower() for t in module['tags']]
                    module_level = self._determine_module_level(module['title'])
                    
                    # Check if module matches user's level and weak topics
                    if module_level == level and any(t in weak_topics for t in module_tags):
                        recommended.append(module)
        
        # If no weak topic matches, recommend based on level
        if not recommended:
            for course in self.courses:
                if course['name'].lower() == course_name.lower():
                    for module in course['submodules']:
                        module_level = self._determine_module_level(module['title'])
                        if module_level == level:
                            recommended.append(module)
        
        # Limit to 3 recommendations
        return recommended[:3]
    
    def _determine_module_level(self, title):
        title_lower = title.lower()
        if 'advanced' in title_lower:
            return 'advanced'
        elif 'intermediate' in title_lower:
            return 'intermediate'
        return 'beginner'
    
    def get_course_module(self, course_name, module_title):
        for course in self.courses:
            if course['name'].lower() == course_name.lower():
                for module in course['submodules']:
                    if module['title'].lower() == module_title.lower():
                        return module
        return None
    
    def evaluate_pre_assessment(self,course_name, user_email, answers):
        try:
            # Get the correct answers for this course
            questions = self.generate_pre_assessment(course_name, user_email)
            
            # Calculate score
            score = 0
            weak_topics = []
            
            for i, question in enumerate(questions, start=1):
                user_answer = answers.get(f'q{i}')
                correct_answer = question['correct_answer']  # Assuming this exists in your question structure
                
                if user_answer == correct_answer:
                    score += 1
                else:
                    weak_topics.append(question['topic'])  # Assuming each question has a 'topic' field
            
            # Determine new level based on score
            total = len(questions)
            percentage = (score / total) * 100
            
            if percentage >= 80:
                new_level = "advanced"
            elif percentage >= 50:
                new_level = "intermediate"
            else:
                new_level = "beginner"
            
            return {
                'score': score,
                'total': total,
                'weak_topics': weak_topics,
                'new_level': new_level
            }
            
        except Exception as e:
            print(f"Error in evaluate_pre_assessment: {str(e)}")
            raise  # Re-raise the exception to be caught by the route handler
    def get_all_courses(self):
        """Return all courses from the courses data file"""
        return self.courses  # This should return the list of courses you loaded in 
    def enroll_user_in_course(self, email, course_name):
        """Enroll a user in a course and update the JSON file"""
        for user in self.users:
            if user['email'] == email:
                if 'courses_enrolled' not in user:
                    user['courses_enrolled'] = []
                if course_name not in user['courses_enrolled']:
                    user['courses_enrolled'].append(course_name)
                    
                    # Initialize progress tracking if not exists
                    if 'progress' not in user:
                        user['progress'] = {}
                    if course_name not in user['progress']:
                        user['progress'][course_name] = {
                            'completed_modules': [],
                            'scores': [],
                            'weak_topics': []
                        }
                    
                    self.save_users()
                    return True
        return False
    
    def generate_pre_assessment(self, course_name, user_email):
        user = self.get_user(user_email)
        if not user:
            return None
        
        course_level = user.get('course_levels', {}).get(course_name, 'beginner')
        
        questions = []
        for topic in self.question_bank:
            if topic['topic'].lower() == course_name.lower():
                for q in topic['questions']:
                    if q['difficulty'].lower() == course_level.lower():
                        formatted_question = {
                            'question': q['question'],
                            'options': q['options'],
                            'correct_answer': q['answer'],  # Add correct answer
                            'difficulty': q['difficulty'],
                            'topic': topic['topic'],  # Add topic for weak areas
                            'related_submodule': q.get('related_submodule', '')
                        }
                        questions.append(formatted_question)
        
        assessment = random.sample(questions, min(10, len(questions))) if questions else []
        return assessment
    def evaluate_module_assessment(self, course_name, module_title, user_email, answers):
        user = self.get_user(user_email)
        if not user:
            return None

        module = self.get_course_module(course_name, module_title)
        if not module or 'assessment' not in module:
            return None

        score = 0
        weak_topics = defaultdict(int)
        question_analysis = []
        
        for i, question in enumerate(module['assessment'], start=1):
            answer_key = f"q_{i}"
            user_answer = answers.get(answer_key, "").strip()
            correct_answer = question['answer'].strip()
            is_correct = user_answer.lower() == correct_answer.lower()
            
            if is_correct:
                score += 1
            else:
                for tag in module.get('tags', []):
                    weak_topics[tag] += 1
            
            question_analysis.append({
                'number': i,
                'question': question['question'],
                'user_answer': user_answer if user_answer else "None",
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'topic': module_title
            })

        total_questions = len(module['assessment'])
        percentage = (score / total_questions) * 100
        passed = percentage >= 70

        # Update user progress
        try:
            updates = {
                'progress': user.get('progress', {})
            }
            
            if course_name not in updates['progress']:
                updates['progress'][course_name] = {
                    'completed_modules': [],
                    'scores': [],
                    'weak_topics': []
                }
            
            if passed and module_title not in updates['progress'][course_name]['completed_modules']:
                updates['progress'][course_name]['completed_modules'].append(module_title)
            
            updates['progress'][course_name]['scores'].append(score)
            updates['progress'][course_name]['weak_topics'] = list(set(
                updates['progress'][course_name]['weak_topics'] + list(weak_topics.keys())
            ))
            
            self.update_user(user_email, updates)
            
        except Exception as e:
            app.logger.error(f"Error updating user progress: {str(e)}")

        return {
            'score': score,
            'total': total_questions,
            'weak_topics': dict(weak_topics),
            'passed': passed,
            'percentage': int(percentage),
            'question_analysis': question_analysis
        }