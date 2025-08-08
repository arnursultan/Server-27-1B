def get_user_email(strategy, details, backend, response, *args, **kwargs):
    email = details.get('email')

    if backend.name == 'github' and not email:
        headers = {'Authorization': f'token {response.get("access_token")}'}
        emails = backend.get_json('https://api.github.com/user/emails', headers=headers)
        email = next((item['email'] for item in emails if item.get('primary')),None)

    if email:
        details['email'] = email
    else:
        raise ValueError('Не удалось получить email от OAuth-провайдера')