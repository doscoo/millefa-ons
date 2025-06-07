import jwt # Utiliser PyJWT pour le décodage initial de l'en-tête, ou rester avec python-jose si elle le permet facilement.
          # python-jose est déjà utilisé pour jwk, donc restons cohérent si possible.
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache # Pour mettre en cache les clés JWKS
from rest_framework import authentication
from rest_framework import exceptions
import requests
from jose import jwk, jwt as jose_jwt # Renommer pour éviter confusion avec PyJWT si les deux sont importés
from jose.utils import base64url_decode
import time # Pour la gestion de l'expiration du cache

class Auth0JSONWebTokenAuthentication(authentication.BaseAuthentication):
    # Récupérer ces valeurs depuis settings.py, qui les chargera depuis .env
    AUTH0_DOMAIN = settings.AUTH0_DOMAIN
    API_IDENTIFIER = settings.API_IDENTIFIER # Audience
    ALGORITHMS = settings.ALGORITHMS # ex: ["RS256"]
    JWKS_CACHE_KEY = "auth0_jwks"
    JWKS_CACHE_TIMEOUT = 24 * 60 * 60  # 24 heures en secondes

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode('utf-8')
        if not auth_header:
            return None

        parts = auth_header.split()

        if parts[0].lower() != 'bearer':
            # Pas un token Bearer, ignorer (pour permettre d'autres méthodes d'auth si besoin)
            return None
        elif len(parts) == 1:
            raise exceptions.AuthenticationFailed('Token not found after Bearer')
        elif len(parts) > 2:
            raise exceptions.AuthenticationFailed('Authorization header must be Bearer token')

        token = parts[1]

        try:
            # 1. Récupérer la clé publique appropriée depuis Auth0 JWKS
            public_key = self._get_public_key(token)
            if not public_key:
                raise exceptions.AuthenticationFailed('Public key for token signature not found.')

            # 2. Valider le token
            payload = jose_jwt.decode(
                token,
                public_key,
                algorithms=self.ALGORITHMS,
                audience=self.API_IDENTIFIER,
                issuer=f"https://{self.AUTH0_DOMAIN}/"
            )

            # 3. Token valide, récupérer ou créer un utilisateur Django
            # Le 'sub' claim est l'identifiant unique de l'utilisateur dans Auth0
            auth0_user_id = payload.get('sub')
            if not auth0_user_id:
                raise exceptions.AuthenticationFailed('Token payload invalid: missing sub (user ID).')

            # Utiliser le sub comme username, ou un champ dédié dans un UserProfile
            user, created = User.objects.get_or_create(username=auth0_user_id)
            if created:
                user.set_unusable_password() # Pas de mot de passe local géré par Django
                # On pourrait vouloir remplir email, first_name, last_name si présents dans le token
                user.email = payload.get('email', '') # Exemple, si 'email' est un scope demandé
                user.save()

            return (user, token)

        except jose_jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired.')
        except jose_jwt.JWTClaimsError as e:
            raise exceptions.AuthenticationFailed(f'Token claims invalid: {e}')
        except jose_jwt.JWTError as e: # Erreur générique de jose_jwt
            raise exceptions.AuthenticationFailed(f'Error decoding token: {e}')
        except Exception as e: # Autres erreurs (ex: problème réseau pour JWKS)
            # Logguer l'erreur e pour le debug
            print(f"Auth0 Authentication Error: {e}")
            raise exceptions.AuthenticationFailed('Error during token validation.')


    def _get_jwks(self):
        jwks = cache.get(self.JWKS_CACHE_KEY)
        if jwks:
            return jwks

        if not self.AUTH0_DOMAIN:
            # Logguer cette erreur ou la remonter de manière appropriée
            print("AUTH0_DOMAIN is not configured.")
            return None

        try:
            jwks_url = f"https://{self.AUTH0_DOMAIN}/.well-known/jwks.json"
            response = requests.get(jwks_url, timeout=10) # timeout de 10s
            response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
            jwks = response.json()
            cache.set(self.JWKS_CACHE_KEY, jwks, self.JWKS_CACHE_TIMEOUT)
            return jwks
        except requests.exceptions.RequestException as e:
            # Logguer l'erreur e
            print(f"Failed to fetch JWKS: {e}")
            # Optionnel: si on a un ancien cache, on pourrait le retourner pour augmenter la résilience
            # mais cela signifie qu'on pourrait utiliser des clés obsolètes.
            # Pour l'instant, on échoue si on ne peut pas récupérer les clés fraîches.
            return None

    def _get_public_key(self, token):
        jwks = self._get_jwks()
        if not jwks or 'keys' not in jwks:
            # Log this condition or raise an exception if appropriate
            print("JWKS not found or 'keys' attribute missing.")
            return None

        try:
            unverified_header = jose_jwt.get_unverified_header(token)
        except jose_jwt.JWTError as e:
            print(f"Error decoding unverified header: {e}")
            return None # Impossible de décoder l'en-tête du token

        if 'kid' not in unverified_header:
            print("Token header does not contain 'kid' (key ID).")
            return None

        rsa_key = {}
        for key_dict in jwks['keys']:
            if key_dict.get('kid') == unverified_header.get('kid'):
                # Construire la clé publique au format attendu par python-jose
                # à partir des composants JWK (n, e, kty, kid, alg, use)
                rsa_key = {
                    "kty": key_dict.get("kty"),
                    "kid": key_dict.get("kid"),
                    "use": key_dict.get("use"),
                    "n": key_dict.get("n"),
                    "e": key_dict.get("e")
                }
                # python-jose peut construire la clé à partir de ce dictionnaire
                # Make sure ALGORITHMS is not empty and contains valid algorithm names
                algo = self.ALGORITHMS[0] if self.ALGORITHMS and isinstance(self.ALGORITHMS, list) and len(self.ALGORITHMS) > 0 else "RS256"
                return jwk.construct(rsa_key, algorithm=algo)

        print(f"Public key with kid='{unverified_header.get('kid')}' not found in JWKS.")
        return None
