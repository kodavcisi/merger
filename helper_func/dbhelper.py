import sqlite3

class Database:

    def __init__(self):
        self.conn = sqlite3.connect('muxdb.sqlite', check_same_thread=False)

    def setup(self):
        # Ana tablo
        cmd = """CREATE TABLE IF NOT EXISTS muxbot(
        user_id INT,
        vid_name TEXT,
        sub_name TEXT,
        filename TEXT,
        thumbnail TEXT
        );"""
        
        self.conn.execute(cmd)
        self.conn.commit()
        
        # Thumbnail kolonunu ekle (eğer eski veritabanı varsa)
        try:
            self.conn.execute('ALTER TABLE muxbot ADD COLUMN thumbnail TEXT')
            self.conn.commit()
        except:
            # Kolon zaten varsa hata verir, geç
            pass
        
        return self.conn

    def put_video(self, user_id, vid_name, filename):
        ins_cmd = 'INSERT INTO muxbot VALUES (?,?,?,?,?);'
        srch_cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        up_cmd = f'UPDATE muxbot SET vid_name="{vid_name}", filename="{filename}" WHERE user_id={user_id};'
        data = (user_id, vid_name, None, filename, None)
        res = self.conn.execute(srch_cmd).fetchone()
        if res:
            self.conn.execute(up_cmd)
            self.conn.commit()
        else:
            self.conn.execute(ins_cmd, data)
            self.conn.commit()

    def put_sub(self, user_id, sub_name):
        ins_cmd = 'INSERT INTO muxbot VALUES (?,?,?,?,?);'
        srch_cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        up_cmd = f'UPDATE muxbot SET sub_name="{sub_name}" WHERE user_id={user_id};'
        data = (user_id, None, sub_name, None, None)
        
        res = self.conn.execute(srch_cmd).fetchone()
        if res:
            self.conn.execute(up_cmd)
            self.conn.commit()
        else:
            self.conn.execute(ins_cmd, data)
            self.conn.commit()

    def check_sub(self, user_id):
        srch_cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        res = self.conn.execute(srch_cmd).fetchone()
        if res:
            sub_file = res[2]
            if sub_file:
                return True
            else:
                return False
        else:
            return False

    def check_video(self, user_id):
        srch_cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        res = self.conn.execute(srch_cmd).fetchone()
        if res:
            vid_file = res[1]
            if vid_file:
                return True
            else:
                return False
        else:
            return False

    def get_vid_filename(self, user_id):
        cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        res = self.conn.execute(cmd).fetchone()
        if res:
            return res[1]
        else:
            return False

    def get_sub_filename(self, user_id):
        cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        res = self.conn.execute(cmd).fetchone()
        if res:
            return res[2]
        else:
            return False

    def get_filename(self, user_id):
        cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
        res = self.conn.execute(cmd).fetchone()
        if res:
            return res[3]
        else:
            return False

    def erase(self, user_id):
        erase_cmd = f'DELETE FROM muxbot WHERE user_id={user_id};'
        try:
            self.conn.execute(erase_cmd)
            self.conn.commit()
            return True
        except:
            return False

    # Thumbnail fonksiyonları
    def set_thumbnail(self, user_id, thumbnail):
        """Kullanıcı için özel thumbnail ayarla"""
        try:
            srch_cmd = f'SELECT * FROM muxbot WHERE user_id={user_id};'
            res = self.conn.execute(srch_cmd).fetchone()
            
            if res:
                # Güncelle
                up_cmd = f'UPDATE muxbot SET thumbnail=? WHERE user_id={user_id};'
                self.conn.execute(up_cmd, (thumbnail,))
            else:
                # Yeni kayıt ekle
                ins_cmd = 'INSERT INTO muxbot VALUES (?,?,?,?,?);'
                data = (user_id, None, None, None, thumbnail)
                self.conn.execute(ins_cmd, data)
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error setting thumbnail: {e}")
            return False

    def get_thumbnail(self, user_id):
        """Kullanıcının özel thumbnail'ini getir"""
        try:
            cmd = f'SELECT thumbnail FROM muxbot WHERE user_id={user_id};'
            res = self.conn.execute(cmd).fetchone()
            if res and res[0]:
                return res[0]
            return None
        except Exception as e:
            print(f"Error getting thumbnail: {e}")
            return None
