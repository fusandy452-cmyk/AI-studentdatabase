# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
import shutil
from datetime import datetime
import json
import logging

app = Flask(__name__)
CORS(app, origins=["https://aistudent.zeabur.app", "https://aistudentbackend.zeabur.app"])

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path=None):
        # 使用環境變數或預設路徑
        if db_path is None:
            # 優先使用 Zeabur 持久化目錄
            persistent_dir = os.getenv('ZEABUR_PERSISTENT_DIR', '/data')
            # 如果沒有持久化目錄，使用 /tmp 但會定期備份
            if not os.path.exists(persistent_dir):
                persistent_dir = '/tmp'
                print('Warning: Using /tmp directory, data may be lost on restart')
            # 確保目錄存在
            os.makedirs(persistent_dir, exist_ok=True)
            self.db_path = os.path.join(persistent_dir, 'ai_study_advisor.db')
            print(f'Database path: {self.db_path}')
            print(f'Persistent directory exists: {os.path.exists(persistent_dir)}')
            print(f'Database file exists: {os.path.exists(self.db_path)}')
        else:
            self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """獲取資料庫連接"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """初始化資料庫和表格"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 啟用 WAL 模式以提高並發性和數據安全性
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=FULL')
        cursor.execute('PRAGMA cache_size=1000')
        cursor.execute('PRAGMA temp_store=MEMORY')
        
        # 用戶資料表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                email TEXT,
                name TEXT,
                avatar TEXT,
                provider TEXT DEFAULT 'google',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 用戶設定資料表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                user_role TEXT NOT NULL,
                student_name TEXT,
                student_email TEXT,
                parent_name TEXT,
                parent_email TEXT,
                relationship TEXT,
                child_name TEXT,
                child_email TEXT,
                citizenship TEXT,
                gpa REAL,
                degree TEXT,
                countries TEXT,
                budget INTEGER,
                target_intake TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 聊天記錄表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                message_content TEXT NOT NULL,
                language TEXT DEFAULT 'zh',
                user_role TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES user_profiles (profile_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 使用統計表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                profile_id TEXT,
                action_type TEXT NOT NULL,
                action_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (profile_id) REFERENCES user_profiles (profile_id)
            )
        ''')
        
        # 留學進度追蹤表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                progress_category TEXT NOT NULL,
                progress_item TEXT NOT NULL,
                status TEXT NOT NULL,
                completion_percentage INTEGER DEFAULT 0,
                notes TEXT,
                target_date DATE,
                completed_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES user_profiles (profile_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 聊天摘要表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                summary_period TEXT NOT NULL,
                summary_content TEXT NOT NULL,
                key_topics TEXT,
                action_items TEXT,
                advisor_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES user_profiles (profile_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 建立管理員表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'advisor',
                permissions TEXT NOT NULL DEFAULT 'read_only',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                created_by TEXT
            )
        ''')
        
        # 建立管理員會話表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                session_id TEXT PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (admin_id) REFERENCES admins (admin_id)
            )
        ''')
        
        # 用戶設定表格
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                email_notifications BOOLEAN DEFAULT 0,
                push_notifications BOOLEAN DEFAULT 1,
                notification_frequency TEXT DEFAULT 'daily',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info('Database initialized successfully at: {}'.format(self.db_path))
    
    def create_backup(self):
        """創建資料庫備份"""
        try:
            # 優先使用持久化目錄的備份路徑
            backup_dirs = [
                '/data/backups',  # Zeabur 持久化目錄
                os.path.join(os.path.dirname(self.db_path), 'backups'),  # 相對路徑
                './backups'  # 當前目錄
            ]
            
            backup_dir = None
            for backup_path in backup_dirs:
                try:
                    os.makedirs(backup_path, exist_ok=True)
                    # 測試是否可寫入
                    test_file = os.path.join(backup_path, 'test_write')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    backup_dir = backup_path
                    logger.info(f'Using backup directory: {backup_dir}')
                    break
                except Exception as e:
                    logger.warning(f'Cannot use backup directory {backup_path}: {e}')
                    continue
            
            if not backup_dir:
                logger.warning('No writable backup directory found')
                return
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f'ai_study_advisor_backup_{timestamp}.db')
            
            shutil.copy2(self.db_path, backup_path)
            logger.info(f'Database backup created: {backup_path}')
            
            # 只保留最近 5 個備份
            backup_files = sorted([f for f in os.listdir(backup_dir) if f.startswith('ai_study_advisor_backup_')])
            for old_backup in backup_files[:-5]:
                os.remove(os.path.join(backup_dir, old_backup))
                
        except Exception as e:
            logger.error(f'Backup creation failed: {e}')

# 初始化資料庫管理器
try:
    db = DatabaseManager()
    logger.info("Database service initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    db = None

# API 端點

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查"""
    try:
        if db:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM user_profiles')
            profile_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM chat_messages')
            message_count = cursor.fetchone()[0]
            conn.close()
            
            return jsonify({
                'status': 'healthy',
                'database_path': db.db_path,
                'user_count': user_count,
                'profile_count': profile_count,
                'message_count': message_count,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Database not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/users', methods=['POST'])
def save_user():
    """儲存用戶資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        user_data = request.get_json()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, email, name, avatar, provider, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_data['userId'],
            user_data.get('email'),
            user_data.get('name'),
            user_data.get('avatar'),
            user_data.get('provider', 'google'),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True, 'message': 'User saved successfully'})
    except Exception as e:
        logger.error(f'Error saving user: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """獲取用戶資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [description[0] for description in cursor.description]
            user_data = dict(zip(columns, row))
            return jsonify({'ok': True, 'data': user_data})
        else:
            return jsonify({'ok': False, 'error': 'User not found'}), 404
    except Exception as e:
        logger.error(f'Error getting user: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>/profiles', methods=['GET'])
def get_user_profiles(user_id):
    """獲取用戶的設定資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM user_profiles WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        profiles = []
        for row in rows:
            # 解析 countries JSON
            countries = []
            if row[14]:  # countries 欄位
                try:
                    countries = json.loads(row[14])
                except:
                    countries = []
            
            profiles.append({
                'id': row[0],
                'profile_id': row[1],
                'user_id': row[2],
                'user_role': row[3],
                'student_name': row[4],
                'student_email': row[5],
                'parent_name': row[6],
                'parent_email': row[7],
                'relationship': row[8],
                'child_name': row[9],
                'child_email': row[10],
                'citizenship': row[11],
                'gpa': row[12],
                'degree': row[13],
                'countries': countries,
                'budget': row[15],
                'target_intake': row[16],
                'created_at': row[17],
                'updated_at': row[18]
            })
        
        return jsonify({'ok': True, 'data': profiles})
    except Exception as e:
        logger.error(f'Error getting user profiles: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/profiles', methods=['POST'])
def save_user_profile():
    """儲存用戶設定資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        profile_data = request.get_json()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 將 countries 列表轉換為 JSON 字串
        countries_json = json.dumps(profile_data.get('countries', []))
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (
                profile_id, user_id, user_role, student_name, student_email,
                parent_name, parent_email, relationship, child_name, child_email,
                citizenship, gpa, degree, countries, budget, target_intake, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profile_data['profile_id'],
            profile_data['user_id'],
            profile_data.get('user_role'),
            profile_data.get('student_name'),
            profile_data.get('student_email'),
            profile_data.get('parent_name'),
            profile_data.get('parent_email'),
            profile_data.get('relationship'),
            profile_data.get('child_name'),
            profile_data.get('child_email'),
            profile_data.get('citizenship'),
            profile_data.get('gpa'),
            profile_data.get('degree'),
            countries_json,
            profile_data.get('budget'),
            profile_data.get('target_intake'),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        
        # 創建備份
        db.create_backup()
        
        return jsonify({'ok': True, 'message': 'Profile saved successfully'})
    except Exception as e:
        logger.error(f'Error saving user profile: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/profiles/<profile_id>', methods=['GET'])
def get_user_profile(profile_id):
    """根據 profile_id 獲取單個用戶設定資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM user_profiles WHERE profile_id = ?', (profile_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # 解析 countries JSON
            countries = []
            if row[14]:  # countries 欄位
                try:
                    countries = json.loads(row[14])
                except:
                    countries = []
            
            profile_data = {
                'id': row[0],
                'profile_id': row[1],
                'user_id': row[2],
                'user_role': row[3],
                'student_name': row[4],
                'student_email': row[5],
                'parent_name': row[6],
                'parent_email': row[7],
                'relationship': row[8],
                'child_name': row[9],
                'child_email': row[10],
                'citizenship': row[11],
                'gpa': row[12],
                'degree': row[13],
                'countries': countries,
                'budget': row[15],
                'target_intake': row[16],
                'created_at': row[17],
                'updated_at': row[18]
            }
            return jsonify({'ok': True, 'data': profile_data})
        else:
            return jsonify({'ok': False, 'error': 'Profile not found'}), 404
    except Exception as e:
        logger.error(f'Error getting user profile: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/profiles/<profile_id>', methods=['PUT'])
def update_user_profile(profile_id):
    """更新用戶設定資料"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        data = request.get_json()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 準備更新資料
        update_fields = []
        update_values = []
        
        if 'student_name' in data:
            update_fields.append('student_name = ?')
            update_values.append(data['student_name'])
        if 'student_email' in data:
            update_fields.append('student_email = ?')
            update_values.append(data['student_email'])
        if 'parent_name' in data:
            update_fields.append('parent_name = ?')
            update_values.append(data['parent_name'])
        if 'parent_email' in data:
            update_fields.append('parent_email = ?')
            update_values.append(data['parent_email'])
        if 'relationship' in data:
            update_fields.append('relationship = ?')
            update_values.append(data['relationship'])
        if 'child_name' in data:
            update_fields.append('child_name = ?')
            update_values.append(data['child_name'])
        if 'child_email' in data:
            update_fields.append('child_email = ?')
            update_values.append(data['child_email'])
        if 'citizenship' in data:
            update_fields.append('citizenship = ?')
            update_values.append(data['citizenship'])
        if 'gpa' in data:
            update_fields.append('gpa = ?')
            update_values.append(data['gpa'])
        if 'degree' in data:
            update_fields.append('degree = ?')
            update_values.append(data['degree'])
        if 'countries' in data:
            update_fields.append('countries = ?')
            update_values.append(json.dumps(data['countries']))
        if 'budget' in data:
            update_fields.append('budget = ?')
            update_values.append(data['budget'])
        if 'target_intake' in data:
            update_fields.append('target_intake = ?')
            update_values.append(data['target_intake'])
        if 'user_role' in data:
            update_fields.append('user_role = ?')
            update_values.append(data['user_role'])
        
        # 添加更新時間
        update_fields.append('updated_at = ?')
        update_values.append(datetime.now().isoformat())
        
        # 添加 WHERE 條件
        update_values.append(profile_id)
        
        if update_fields:
            sql = f"UPDATE user_profiles SET {', '.join(update_fields)} WHERE profile_id = ?"
            cursor.execute(sql, update_values)
            conn.commit()
            
        conn.close()
        
        return jsonify({'ok': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        logger.error(f'Error updating user profile: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/messages', methods=['POST'])
def save_chat_message():
    """儲存聊天記錄"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        message_data = request.get_json()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_messages (
                profile_id, user_id, message_type, message_content, language, user_role
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            message_data.get('profile_id'),
            message_data.get('user_id'),
            message_data.get('message_type'),  # 'user' or 'ai'
            message_data.get('message_content'),
            message_data.get('language', 'zh'),
            message_data.get('user_role')
        ))
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True, 'message': 'Message saved successfully'})
    except Exception as e:
        logger.error(f'Error saving chat message: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/messages/<profile_id>', methods=['GET'])
def get_chat_messages(profile_id):
    """獲取聊天記錄"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        limit = request.args.get('limit', 100, type=int)
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chat_messages WHERE profile_id = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (profile_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'profile_id': row[1],
                'user_id': row[2],
                'message_type': row[3],
                'message_content': row[4],
                'language': row[5],
                'user_role': row[6],
                'created_at': row[7]
            })
        
        return jsonify({'ok': True, 'data': messages})
    except Exception as e:
        logger.error(f'Error getting chat messages: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['POST'])
def save_usage_stat():
    """儲存使用統計"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        stat_data = request.get_json()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        action_details = json.dumps(stat_data.get('action_details', {}))
        cursor.execute('''
            INSERT INTO usage_stats (user_id, profile_id, action_type, action_details)
            VALUES (?, ?, ?, ?)
        ''', (
            stat_data.get('user_id'),
            stat_data.get('profile_id'),
            stat_data.get('action_type'),
            action_details
        ))
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True, 'message': 'Usage stat saved successfully'})
    except Exception as e:
        logger.error(f'Error saving usage stat: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_usage_stats():
    """獲取使用統計"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        days = request.args.get('days', 30, type=int)
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                action_type,
                COUNT(*) as count
            FROM usage_stats 
            WHERE created_at >= datetime('now', '-{} days')
            GROUP BY DATE(created_at), action_type
            ORDER BY date DESC
        '''.format(days))
        
        rows = cursor.fetchall()
        conn.close()
        
        stats = []
        for row in rows:
            stats.append({
                'date': row[0],
                'action_type': row[1],
                'count': row[2]
            })
        
        return jsonify({'ok': True, 'data': stats})
    except Exception as e:
        logger.error(f'Error getting usage stats: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/backup', methods=['POST'])
def create_backup():
    """創建資料庫備份"""
    try:
        if not db:
            return jsonify({'ok': False, 'error': 'Database not available'}), 500
            
        db.create_backup()
        return jsonify({'ok': True, 'message': 'Backup created successfully'})
    except Exception as e:
        logger.error(f'Error creating backup: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """根路徑"""
    return jsonify({
        'service': 'AI Study Advisor Database Service',
        'status': 'running',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'endpoints': [
            '/health',
            '/api/users',
            '/api/profiles',
            '/api/messages',
            '/api/stats',
            '/api/backup'
        ]
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting Database Service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
