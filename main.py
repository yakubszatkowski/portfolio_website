from flask import Flask, render_template, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Api, Resource, fields, marshal, abort
from sqlalchemy.dialects.postgresql import ENUM
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
import os
from datetime import datetime, timedelta
from dateutil import relativedelta


app = Flask(__name__)
api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('portfolio_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('jwt_secret_key')
app.config["JWT_ALGORITHM"] = "HS256"
db = SQLAlchemy(app)
jwt = JWTManager(app)


class Translation(db.Model):
    __tablename__ = "Translations"
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer, nullable=False)
    object_type = db.Column(ENUM('softskill', 'myproject', 'technology', 'subtechnology', 'experience',
        name='object_types'), nullable=False)
    language = db.Column(db.String)
    title = db.Column(db.String)
    text = db.Column(db.String)


class SoftSkill(db.Model):
    __tablename__ = 'Softskills'
    id = db.Column(db.Integer, primary_key=True)
    type_soft = db.Column(db.String)  # either aboutme, language, soft skill, interest
    translations = db.relationship(  # this contains both title and text and translations for them
        'Translation',
        primaryjoin="and_(Translation.object_type == 'softskill', foreign(Translation.object_id) == SoftSkill.id)",
        lazy='dynamic',
        overlaps="translations" # addresses SAWarning
    )


class MyProject(db.Model):
    __tablename__ = 'Projects'
    id = db.Column(db.Integer, primary_key=True)
    subtechnologies_used = db.Column(db.String) # doesn't require translation
    image_path = db.Column(db.String)
    link = db.Column(db.String)
    translations = db.relationship(
        'Translation',
        primaryjoin="and_(Translation.object_type == 'myproject', foreign(Translation.object_id) == MyProject.id)",
        lazy='dynamic',
        overlaps="translations"
    )


class Technology(db.Model):
    __tablename__ = 'Technologies'
    id = db.Column(db.Integer, primary_key=True)
    subtechnologies = db.relationship('Subtechnology', backref='technology')
    technology_name = db.Column(db.String(50), nullable=False, unique=True) # doesn't require translation
    translations = db.relationship(
        'Translation',
        primaryjoin="and_(Translation.object_type == 'technology', foreign(Translation.object_id) == Technology.id)",
        lazy='dynamic',
        overlaps="translations"
    )


class Subtechnology(db.Model):
    __tablename__ = 'Subtechnologies'
    id = db.Column(db.Integer, primary_key=True)
    technology_name = db.Column(db.String, db.ForeignKey(Technology.technology_name))
    subtechnology_name = db.Column(db.String(50), nullable=False) # doesn't require translation
    translations = db.relationship(
        'Translation',
        primaryjoin="and_(Translation.object_type == 'subtechnology', foreign(Translation.object_id) == Subtechnology.id)",
        lazy='dynamic',
        overlaps="translations"
    )


class Experience(db.Model):
    __tablename__ = 'Experiences'
    id = db.Column(db.Integer, primary_key=True)
    type_exp = db.Column(db.String)  # either work or education # either aboutme, language, soft skill, interest
    location = db.Column(db.String)
    time_range = db.Column(db.String)
    translations = db.relationship(
        'Translation',
        primaryjoin="and_(Translation.object_type == 'experience', foreign(Translation.object_id) == Experience.id)",
        lazy='dynamic',
        overlaps="translations"
    )


resource_fields = {
    'id': fields.Integer,
    'type_soft': fields.String,
    'type_exp': fields.String,
    'subtechnologies_used': fields.String,
    'image_path': fields.String,
    'link': fields.String,
    'technology_name': fields.String,
    'subtechnologies': fields.List(
        fields.Nested({'id': fields.Integer,
                       'subtechnology_name': fields.String,
                       'translations': fields.List(
                           fields.Nested({'id': fields.Integer,
                                          'language': fields.String,
                                          'text': fields.String}))})),
    'subtechnology_name': fields.String,
    'location': fields.String,
    'time_range': fields.String,
    'translations': fields.List(
        fields.Nested({
            'id': fields.Integer,
            'language': fields.String(attribute='language'),
            'title': fields.String(attribute='title'),
            'text': fields.String(attribute='text')})),
    'object_type': fields.String,
    'object_id': fields.Integer,
    'language': fields.String,
    'title': fields.String(attribute='title'),
    'text': fields.String
}


def content_by_language(contents, language):
    contents['Contact'] = [{'contact': None}]
    titles_translation = {
        'About me': 'O mnie',
        'My projects': 'Moje projekty',
        'Technical skills': 'Umiejętności techniczne',
        'Work experience': 'Doświadczenie zawodowe',
        'Education': 'Edukacja',
        'Languages': 'Języki',
        'Soft skills': 'Umiejętności miękkie',
        'Interests': 'Zainteresowania',
        'Contact': 'Kontakt',
    }

    if language == 'pl':
        for key in titles_translation:
            contents[titles_translation[key]] = contents.pop(key)

    if language == 'pl':  # makeshift fix
        if 'Edukacja' in contents:
            for polish_dict in contents['Edukacja']:
                polish_dict['location'] = 'Uniwersytet Śląski, Katowice'


    for key, section in contents.items():
        for subsection in section:
            if 'translations' in subsection:
                translations = subsection['translations']
                translations = [translation for translation in translations if translation['language'] == language]
                subsection['translations'] = dict(translations[0])
            elif 'subtechnologies' in subsection:
                subtechnologies = subsection['subtechnologies']
                for subtechnology in subtechnologies:
                    translations = subtechnology['translations']
                    translations = [translation for translation in translations if translation['language'] == language]
                    subtechnology['translations'] = dict(translations[0])
                subsection['subtechnologies'] = [dict(subtechnology) for subtechnology in subsection['subtechnologies']]


    return contents


def date_output(beginning_date, ending_date=None):
    format_beg_day = datetime.strptime(beginning_date, '%m-%Y')
    if ending_date:
        format_end_day = datetime.strptime(ending_date, '%m-%Y')
        works_here = False
    else:
        format_end_day = datetime.today()
        works_here = True

    delta = relativedelta.relativedelta(format_end_day, format_beg_day)
    years = delta.years
    months = delta.months

    output = f'{beginning_date} - {"Now" if works_here else ending_date}{", " if months or years != 0 else ", just started!"}'

    if years > 0:
        output += f'{years} year{"s" if years > 1 else ""} '
    if months > 0:
        output += f'{months} month{"s" if months > 1 else ""}'

    return output


def marshal_wo_null(content):
    content_marshal = marshal(content, resource_fields)
    content_marshal_wo_null = {k: v for (k, v) in content_marshal.items() if v is not None and v != 0 and v}
    return content_marshal_wo_null


def marshall_all(table, var=None):
    query = [marshal_wo_null(item) for item in db.session.query(table).all()]
    list_of_contents = [content for content in query if content.get('type_soft') == var or content.get('type_exp') == var]
    return list_of_contents


class GetContent(Resource):
    def get(self):
        args = request.args
        content_type = args['content']
        content_id = args['id']
        got_content = globals().get(content_type).query.filter_by(id=content_id).first()
        if not got_content:
            abort(404, message='Couldn\'t find requested content')
        else:
            return marshal_wo_null(got_content), 200


class GetAllContent(Resource):
    def get(self):
        getall = {
            'About me': marshall_all(SoftSkill, 'aboutme'),
            'My projects': marshall_all(MyProject),
            'Technical skills': marshall_all(Technology),
            'Work experience': marshall_all(Experience, 'work'),
            'Education': marshall_all(Experience, 'education'),
            'Languages': marshall_all(SoftSkill, 'language'),
            'Soft skills': marshall_all(SoftSkill, 'soft skill'),
            'Interests': marshall_all(SoftSkill, 'interest')
        }
        return getall


class PutContent(Resource):
    @jwt_required()
    def put(self):
        args = request.form
        content_type = args['content']
        content_id = args['id']

        if content_type == 'SoftSkill':
            new_content = SoftSkill(
                id=content_id,
                type_soft=args['type_soft']
            )

        elif content_type == 'MyProject':
            new_content = MyProject(
                id=content_id,
                subtechnologies_used=args['subtechnologies_used'],
                image_path=args['image_path'],
                link=args['github_link']
            )

        elif content_type == 'Technology':
            new_content = Technology(
                id=content_id,
                technology_name=args['technology_name']
            )

        elif content_type == 'Subtechnology':
            new_content = Subtechnology(
                id=content_id,
                technology_name=args['technology_name'],
                subtechnology_name=args['subtechnology_name']
            )

        elif content_type == 'Experience':
            new_content = Experience(
                id=content_id,
                type_exp=args['type_exp'], # either work or education
                location=args['location'],
                time_range=date_output(args['starting_date'], args['ending_date'])
            )

        else:
            return 'Wrong content key', 400

        object_to_update = globals().get(content_type).query.filter_by(id=content_id).first()
        if object_to_update:
            for column_name in object_to_update.__table__.columns.keys()[1:]:
                new_value = getattr(new_content, column_name)
                setattr(object_to_update, column_name, new_value)
                db.session.commit()
        else:
            db.session.add(new_content)
            db.session.commit()

        return marshal_wo_null(new_content), 200


class PutText(Resource):
    @jwt_required()
    def put(self):
        args = request.form
        translation_id=args['id']
        new_text = Translation(
            id=translation_id,
            object_id=args['object_id'],
            object_type=args['object_type'],
            language=args['language'],
            text=args['text'],
            title=args['title']
        )

        translation_to_replace = Translation.query.filter_by(id=translation_id).first()
        if translation_to_replace:
            for column_name in translation_to_replace.__table__.columns.keys()[1:]:
                new_value = getattr(new_text, column_name)
                setattr(translation_to_replace, column_name, new_value)
                db.session.commit()
        else:
            db.session.add(new_text)
            db.session.commit()

        return marshal_wo_null(new_text)


class DeleteContent(Resource):
    @jwt_required()
    def delete(self):
        args = request.args
        content_type = args['content']
        content_id = args['id']
        got_content = globals().get(content_type).query.filter_by(id=content_id).first()
        if not got_content:
            abort(404, message='Couldn\'t find requested content')
        else:
            db.session.delete(got_content)
            db.session.commit()
            return {'message': f'Content from {content_type} with id {content_id} has been deleted'}, 200


class GetToken(Resource):
    def post(self):
        auth = request.authorization
        if not auth and auth.username == 'admin' and auth.password == os.environ.get('portfolio_password'):
            return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required!:'})

        token = create_access_token(identity='admin', expires_delta=timedelta(hours=8))
        return token

api.add_resource(GetContent, '/get/')
api.add_resource(GetAllContent, '/get-all/')
api.add_resource(PutContent, '/put/')
api.add_resource(PutText, '/put-text/')
api.add_resource(DeleteContent, '/delete/')
api.add_resource(GetToken, '/get-token/')


@app.route('/index')
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/main')
def main_page():
    language = request.args.get('language')
    if language == 'english':
        website_contents = content_by_language(GetAllContent().get(), language='en')
        return render_template('main.html', website_contents=website_contents)
    elif language == 'polish':
        website_contents = content_by_language(GetAllContent().get(), language='pl')
        return render_template('main.html', website_contents=website_contents)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()
