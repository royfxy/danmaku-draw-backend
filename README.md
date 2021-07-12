# danmaku-draw-backend
## Usage
1. Install [NeteaseCloudMusicApi](https://github.com/Binaryify/NeteaseCloudMusicApi)

2. Create a config.json ([template](https://github.com/royfxy/danmaku-draw-backend/blob/main/config_template.json))

3. Create database:

    * canvas:

        | Field    | Type         | Null | Key | Default |
        |----------|--------------|------|-----|---------|
        | pos      | int unsigned | NO   | PRI | NULL    |
        | pixel_id | int unsigned | NO   |     | NULL    |

    * color:

        | Field | Type              | Null | Key | Default | Extra          |
        |-------|-------------------|------|-----|---------|----------------|
        | id    | smallint unsigned | NO   | PRI | NULL    | auto_increment |
        | hex   | varchar(10)       | NO   |     | NULL    |                |

    * pixel_history:
    
        | Field    | Type              | Null | Key | Default | Extra          |
        |----------|-------------------|------|-----|---------|----------------|
        | id       | int unsigned      | NO   | PRI | NULL    | auto_increment |
        | pos      | int               | NO   |     | NULL    |                |
        | time     | timestamp         | NO   |     | NULL    |                |
        | color_id | smallint unsigned | NO   |     | NULL    |                |
        | user_id  | int unsigned      | NO   |     | NULL    |                |

    * user:

        | Field         | Type         | Null | Key | Default |
        |---------------|--------------|------|-----|---------|
        | uid           | int unsigned | NO   | PRI | NULL    |       
        | name          | varchar(20)  | NO   |     | NULL    |       
        | gold_coin     | int unsigned | YES  |     | 0       |       
        | silver_coin   | int unsigned | YES  |     | 0       |       
        | music_ordered | int unsigned | YES  |     | 0       |       
        | dots_drawed   | int unsigned | YES  |     | 0       |       
        | weight        | int          | YES  |     | 50      |       
        | vip_level     | int          | YES  |     | 0       |    

4. Run
    ```
    python ./server.py <--log warning> <--token yourToken>
    ```