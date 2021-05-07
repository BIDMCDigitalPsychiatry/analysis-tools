import LAMP
LAMP.connect()
import requests
import datetime
import pytz
utc = pytz.utc
eastern = pytz.timezone('US/Eastern') # redcap server time

RESEARCHER = 'dnbd16yj2zkegk67aqm8' #college 1000
credentials = {}
lamp_names = {}

def score_pss(record):
    reverse_q={  #reverse score if True (4,5,7,8)
     'pss1': False,
     'pss2': False,
     'pss3': False,
     'pss4': True,
     'pss5': True,
     'pss6': False,
     'pss7': True,
     'pss8': True,
     'pss9': False,
     'pss10': False}
    total=0
    for q in reverse_q :
        if record[q]:
            if not reverse_q[q]: total+=int(record[q])
            elif reverse_q[q]: total+=(4-int(record[q]))
        else:             
            return None
    return total 

redcap_questions={
    'gender':{
        '0':'prefer not to say',
        '1':'female',
        '2':'male',
        '3':'gender non-binary',
        '4':'other'
    },
    'race_ethnicity':{
        '0': 'American Indian or Alaskan Native',
        '1': 'Asian',
        '2': 'Black or African American',
        '3': 'Latinx',
        '4': 'Native Hawaiian or Pacific Islander',
        '5': 'White',
        '6': 'Other'
    },
    'age':None
    ,
    'year':{
        '0': 'freshman',
        '1': 'sophomore',
        '2': 'junior',
        '3': 'senior',
        '4': 'graduate student'
    },
    'college':None
    ,
    'living':{
        '0': 'on campus',
        '1': 'at home',
        '2': 'off campus'
    },
    'covid19':{
        '0': 'yes',
        '1': 'no',
        '2': 'suspected'
    }
}

manual_ids = LAMP.Type.get_attachment(RESEARCHER, 'org.digitalpsych.redcap.id_matching')['data']

records = LAMP.Type.get_attachment(RESEARCHER, 'org.digitalpsych.redcap.data')['data']

# Get all emails used in lamp credentials and names
for study in LAMP.Study.all_by_researcher(RESEARCHER)['data']:
    print("getting emails for:", study['name'], '...')
    for part in LAMP.Participant.all_by_study(study['id'])['data']:
        if part['id'] not in manual_ids['skip'].values(): 
            credential = LAMP.Credential.list(part['id'])['data']
            if len(credential)>0:
                for c in credential :
                    credentials[c['access_key'].lower()]=c['origin']
            try:
                lamp_name = LAMP.Type.get_attachment(part['id'], 'lamp.name')['data'].lower()
                lamp_names[lamp_name] = part['id']
            except Exception: 
                pass

# Set attachment for matched records
print('Setting attachments...')
count = 0
for record in records:
    lamp_id = None
    demographics={}
    if record['enrollment_survey_complete'] == '2' and record['record_id'] not in manual_ids['skip']:
        preferred_email = record['preferred_email'].lower()
        student_email = record['student_email'].lower()

        # Search for a lamp id match from credentials
        if record['record_id'] in manual_ids['match']:
            lamp_id = manual_ids['match'][record['record_id']]
        else:
            lamp_id=credentials.get(preferred_email)
            if not lamp_id: 
                lamp_id=credentials.get(student_email) 

            # If not in credentials, try to match with a lamp.name
            if not lamp_id:
                for lamp_name in lamp_names:
                    if preferred_email in lamp_name:
                        lamp_id = lamp_names[lamp_name]
                        break
                    elif student_email in lamp_name:
                        lamp_id = lamp_names[lamp_name]
                        break
        if not lamp_id: continue


        # Get enrollment timestamp UTC ms
        f = '%Y-%m-%d %H:%M:%S'
        dt_eastern = eastern.localize(datetime.datetime.strptime(record['enrollment_survey_timestamp'],f),is_dst=None)
        dt_utc = dt_eastern.astimezone(utc)
        ts_utc_ms = int(dt_utc.timestamp())*1000
        demographics['timestamp'] = ts_utc_ms

        # Note redcap record id
        demographics['redcap_record'] = record['record_id']

        # Get demographics into a dict
        for question in redcap_questions:
            if question == 'age':
                demographics[question] = int((record[question]))
            elif redcap_questions[question]:
                demographics[question] = redcap_questions[question][(record[question])]
            else:
                demographics[question] = record[question]

        demographics['pss'] = score_pss(record)

        # Set attachment
        if demographics and lamp_id:
            if len(demographics) == 10:
                LAMP.Type.set_attachment(RESEARCHER, lamp_id,
                                         attachment_key='org.digitalpsych.college_study.demographics',
                                         body=demographics)
                count+=1
print(count)