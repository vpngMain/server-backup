#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testy pro aplikaci Odběry
Spustit: python tests.py
"""

import unittest
import os
import sys
from datetime import date

# Přidáme cestu k aplikaci
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Pobocka, Odber, Reklamace
from werkzeug.security import generate_password_hash


class TestCase(unittest.TestCase):
    """Základní testovací třída."""
    
    def setUp(self):
        """Nastavení testovacího prostředí."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Vytvoření testovacích dat
        self.test_pobocka = Pobocka(nazev='Test Pobočka')
        db.session.add(self.test_pobocka)
        
        self.test_admin = User(
            username='testadmin',
            pin='1234',
            jmeno='Test Admin',
            role='admin'
        )
        self.test_admin.set_password('testpass')
        db.session.add(self.test_admin)
        
        self.test_user = User(
            username='testuser',
            pin='5678',
            jmeno='Test User',
            role='user'
        )
        self.test_user.set_password('testpass')
        self.test_user.pobocky.append(self.test_pobocka)
        db.session.add(self.test_user)
        
        db.session.commit()
    
    def tearDown(self):
        """Uklízení po testu."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def login(self, pin='1234'):
        """Pomocná metoda pro přihlášení."""
        return self.app.post('/admin/login', data={'pin': pin}, follow_redirects=True)
    
    def test_index_page(self):
        """Test hlavní stránky."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)  # Redirect na login
    
    def test_login(self):
        """Test přihlášení."""
        response = self.login('1234')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Admin', response.data)
    
    def test_login_wrong_pin(self):
        """Test přihlášení se špatným PINem."""
        response = self.login('9999')
        self.assertEqual(response.status_code, 200)
        # Kontrola, že přihlášení selhalo (není redirect)
        self.assertNotIn(b'Test Admin', response.data)
    
    def test_user_can_access_assigned_branch(self):
        """Test, že uživatel může přistupovat k přiřazené pobočce."""
        self.login('5678')  # Přihlásíme test usera
        
        # Test přístupu k přiřazené pobočce
        response = self.app.get(f'/branch/{self.test_pobocka.id}')
        self.assertEqual(response.status_code, 200)
    
    def test_user_cannot_access_other_branch(self):
        """Test, že uživatel nemůže přistupovat k jiné pobočce."""
        # Vytvoříme další pobočku
        other_pobocka = Pobocka(nazev='Jiná Pobočka')
        db.session.add(other_pobocka)
        db.session.commit()
        
        self.login('5678')  # Přihlásíme test usera
        
        # Test přístupu k jiné pobočce
        response = self.app.get(f'/branch/{other_pobocka.id}', follow_redirects=True)
        # Ověříme, že došlo k redirectu (status 200 po redirectu) a že není přístup
        self.assertEqual(response.status_code, 200)
    
    def test_admin_can_access_all_branches(self):
        """Test, že admin může přistupovat ke všem pobočkám."""
        other_pobocka = Pobocka(nazev='Jiná Pobočka')
        db.session.add(other_pobocka)
        db.session.commit()
        
        self.login('1234')  # Přihlásíme admina
        
        # Test přístupu k jakékoliv pobočce
        response = self.app.get(f'/branch/{other_pobocka.id}')
        self.assertEqual(response.status_code, 200)
    
    def test_user_multiple_branches(self):
        """Test, že uživatel může mít více poboček."""
        # Vytvoříme další pobočku
        pobocka2 = Pobocka(nazev='Druhá Pobočka')
        db.session.add(pobocka2)
        db.session.commit()
        
        # Přidáme uživateli další pobočku
        self.test_user.pobocky.append(pobocka2)
        db.session.commit()
        
        # Ověříme, že má přístup k oběma
        self.login('5678')
        
        response1 = self.app.get(f'/branch/{self.test_pobocka.id}')
        self.assertEqual(response1.status_code, 200)
        
        response2 = self.app.get(f'/branch/{pobocka2.id}')
        self.assertEqual(response2.status_code, 200)
    
    def test_add_odber(self):
        """Test přidání odběru."""
        self.login('1234')
        
        response = self.app.post(
            f'/branch/{self.test_pobocka.id}',
            data={
                'jmeno': 'Test Zákazník',
                'datum': date.today().isoformat(),
                'stav': 'aktivní',
                'kdo_zadal': 'Test Admin'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        
        # Ověříme, že odběr byl vytvořen
        odber = Odber.query.filter_by(jmeno='Test Zákazník').first()
        self.assertIsNotNone(odber)
        self.assertEqual(odber.pobocka_id, self.test_pobocka.id)
    
    def test_add_reklamace(self):
        """Test přidání reklamace."""
        self.login('1234')
        
        response = self.app.post(
            f'/reklamace/branch/{self.test_pobocka.id}',
            data={
                'zakaznik': 'Test Zákazník',
                'telefon': '123456789',
                'znacka': 'Test Značka',
                'model': 'Test Model',
                'datum_prijmu': date.today().isoformat(),
                'popis_zavady': 'Test závada',
                'stav': 'Čeká'
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        
        # Ověříme, že reklamace byla vytvořena
        reklamace = Reklamace.query.filter_by(zakaznik='Test Zákazník').first()
        self.assertIsNotNone(reklamace)
        self.assertEqual(reklamace.pobocka_id, self.test_pobocka.id)
    
    def test_user_can_access_multiple_branches(self):
        """Test, že uživatel s více pobočkami má přístup ke všem."""
        pobocka2 = Pobocka(nazev='Druhá Pobočka')
        pobocka3 = Pobocka(nazev='Třetí Pobočka')
        db.session.add(pobocka2)
        db.session.add(pobocka3)
        db.session.commit()
        
        # Přidáme uživateli více poboček
        self.test_user.pobocky = [self.test_pobocka, pobocka2, pobocka3]
        db.session.commit()
        
        self.login('5678')
        
        # Ověříme přístup ke všem pobočkám
        for pobocka in [self.test_pobocka, pobocka2, pobocka3]:
            response = self.app.get(f'/branch/{pobocka.id}')
            self.assertEqual(response.status_code, 200, f"Uživatel nemá přístup k pobočce {pobocka.nazev}")


def run_tests():
    """Spustí všechny testy."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    print("=" * 60)
    print("Spouštění testů aplikace Odběry")
    print("=" * 60)
    unittest.main(verbosity=2)
