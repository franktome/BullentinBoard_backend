import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# MySQL 데이터베이스 연결 설정
db = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    password="dbg202306",
    database="bulletin_board"
)

# 로그인하는 API
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM member WHERE username = %s AND password = %s"
    cursor.execute(query, (username, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        return jsonify({"message": "Login successful", "user": user}), 200
    else:
        return jsonify({"message": "Invalid username or password"}), 401

# 회원가입 API        
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    created_date = datetime.now().strftime('%Y-%m-%d')
    modified_date = created_date

    cursor = db.cursor()

    # 이메일 중복 검사
    cursor.execute("SELECT * FROM Member WHERE email = %s", (email,))
    existing_user = cursor.fetchone()
    if existing_user:
        cursor.close()
        return jsonify({"message": "Email already exists"}), 400

    # 회원 정보 추가
    cursor.execute(
        "INSERT INTO Member (email, username, password, role, createdDate, modifiedDate) VALUES (%s, %s, %s, %s, %s, %s)",
        (email, username, password, 'USER', created_date, modified_date)
    )
    db.commit()
    cursor.close()
    return jsonify({"message": "Registration successful"}), 201

# 게시글 목록 가져오기
@app.route('/board/list', methods=['GET'])
def get_board_list():
    try:
        # 클라이언트에서 전달된 파라미터 가져오기
        page = int(request.args.get('page', 0))  # 페이지 번호 (0부터 시작)
        size = int(request.args.get('size', 10))  # 페이지 크기
        option = request.args.get('option', None)  # 검색 옵션
        keyword = request.args.get('keyword', None)  # 검색 키워드

        offset = page * size

        cursor = db.cursor(dictionary=True)

        # 기본 쿼리
        base_query = """
            SELECT 
                b.board_id AS id, 
                b.title, 
                b.content, 
                b.viewCount, 
                b.createdDate, 
                m.username AS writer 
            FROM Board b
            LEFT JOIN Member m ON b.member_id = m.id
        """

        # 검색 조건 추가
        where_clause = ""
        query_params = []

        if option and keyword:
            if option == "title":
                where_clause = "WHERE b.title LIKE %s"
                query_params.append(f"%{keyword}%")
            elif option == "content":
                where_clause = "WHERE b.content LIKE %s"
                query_params.append(f"%{keyword}%")
            elif option == "writer":
                where_clause = "WHERE m.username LIKE %s"
                query_params.append(f"%{keyword}%")

        # 전체 게시물 수 쿼리
        count_query = f"SELECT COUNT(*) AS totalElements FROM ({base_query} {where_clause}) AS filtered"
        cursor.execute(count_query, query_params)
        total_elements = cursor.fetchone()["totalElements"]

        # 특정 페이지의 게시물 가져오기 쿼리
        query = f"""
            {base_query}
            {where_clause}
            ORDER BY b.createdDate DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, query_params + [size, offset])
        board_list = cursor.fetchall()

        cursor.close()

        # 전체 페이지 수 계산
        total_pages = (total_elements + size - 1) // size  # 올림 계산

        # 응답 데이터 생성
        response = {
            "content": board_list,  # 현재 페이지 게시물 리스트
            "totalElements": total_elements,  # 전체 게시물 수
            "totalPages": total_pages,  # 전체 페이지 수
        }

        return jsonify(response), 200  # JSON 응답 반환

    except Exception as e:
        return jsonify({"message": "Error fetching board list", "error": str(e)}), 500

# 게시글을 DB의 board 테이블에 저장하는 API
@app.route('/board/write', methods=['POST'])
def write_board():
    data = request.json
    title = data.get('title')
    content = data.get('content')
    writer_id = data.get('writerId')  # React에서 보낸 작성자 ID
    created_date = datetime.now().strftime('%Y-%m-%d')
    modified_date = created_date

    cursor = db.cursor()

    try:
        # Board 테이블에 데이터 삽입
        query = """
            INSERT INTO Board (title, content, viewCount, createdDate, modifiedDate, member_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (title, content, 0, created_date, modified_date, writer_id))
        db.commit()
        board_id = cursor.lastrowid  # 삽입된 레코드의 ID

        return jsonify({"boardId": board_id}), 201  # 생성된 게시글 ID 반환
    except Exception as e:
        db.rollback()
        return jsonify({"message": "게시글 작성 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()


UPLOAD_FOLDER = './uploads'  # 파일 저장 경로
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 폴더가 없으면 생성

# 파일 업로드 하는 API
@app.route('/board/<int:board_id>/file/upload', methods=['POST'])
def upload_file(board_id):
    if 'files' not in request.files:
        return jsonify({"message": "No files part in the request"}), 400

    files = request.files.getlist('files')  # 업로드된 파일 리스트 가져오기
    cursor = db.cursor()

    try:
        for file in files:
            if file and file.filename:
                # 파일 저장
                origin_file_name = secure_filename(file.filename)  # 안전한 파일 이름
                file_path = os.path.join(UPLOAD_FOLDER, origin_file_name)  # 저장 경로 생성
                file.save(file_path)  # 파일 저장

                # 현재 날짜 가져오기
                created_date = datetime.now().strftime('%Y-%m-%d')
                modified_date = created_date

                # 파일 정보 DB에 저장
                query = """
                    INSERT INTO File (originFileName, filePath, createdDate, modifiedDate, board_id)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (origin_file_name, file_path, created_date, modified_date, board_id))

        db.commit()
        return jsonify({"message": "Files uploaded successfully"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error uploading files", "error": str(e)}), 500
    finally:
        cursor.close()

# 조회수 증가 API
@app.route('/board/<int:board_id>/increment-view', methods=['POST'])
def increment_view_count(board_id):
    cursor = None
    try:
        cursor = db.cursor()
        
        # 게시글 존재 여부 확인
        check_query = "SELECT 1 FROM Board WHERE board_id = %s"
        cursor.execute(check_query, (board_id,))
        if cursor.fetchone() is None:
            return jsonify({"message": "게시글을 찾을 수 없습니다."}), 404
        
        # 조회수 증가 처리
        update_query = "UPDATE Board SET viewCount = viewCount + 1 WHERE board_id = %s"
        cursor.execute(update_query, (board_id,))
        db.commit()
        
        return jsonify({"message": "조회수가 증가했습니다."}), 200
    except Exception as e:
        return jsonify({"message": "조회수 증가 중 오류 발생", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()

# 게시글 세부사항 가져오기
@app.route('/board/<int:board_id>', methods=['GET'])
def get_board_detail(board_id):
    cursor = None
    try:
        cursor = db.cursor(dictionary=True)

        # 게시글 정보 조회
        query = """
            SELECT 
                b.board_id AS id, 
                b.title, 
                b.content, 
                b.viewCount, 
                b.createdDate, 
                b.modifiedDate, 
                m.email AS writerEmail,
                m.username AS writerName
            FROM Board b
            LEFT JOIN Member m ON b.member_id = m.id
            WHERE b.board_id = %s
        """
        cursor.execute(query, (board_id,))
        board_detail = cursor.fetchone()

        if not board_detail:
            return jsonify({"message": "게시글을 찾을 수 없습니다."}), 404

        # 첨부파일 정보 조회
        file_query = "SELECT originFileName, filePath FROM File WHERE board_id = %s"
        cursor.execute(file_query, (board_id,))
        files = cursor.fetchall() or []
        board_detail["files"] = files  # 첨부파일 정보 추가

        # # 조회수 증가 처리
        # update_query = "UPDATE Board SET viewCount = viewCount + 1 WHERE board_id = %s"
        # cursor.execute(update_query, (board_id,))
        # db.commit()

        return jsonify(board_detail), 200
    except Exception as e:
        return jsonify({"message": "게시글 상세 조회 중 오류 발생", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()

# 게시글 삭제하는 API
@app.route('/board/<int:board_id>', methods=['DELETE'])
def delete_board(board_id):
    try:
        cursor = db.cursor()

        # 게시글이 존재하는지 확인
        check_query = "SELECT * FROM Board WHERE board_id = %s"
        cursor.execute(check_query, (board_id,))
        board = cursor.fetchone()

        if not board:
            return jsonify({"message": "게시글을 찾을 수 없습니다."}), 404

        # 게시글에 연결된 파일 삭제
        file_query = "SELECT filePath FROM File WHERE board_id = %s"
        cursor.execute(file_query, (board_id,))
        files = cursor.fetchall()

        for file in files:
            file_path = file["filePath"]
            if os.path.exists(file_path):
                os.remove(file_path)  # 파일 삭제

        # 파일 데이터베이스에서 삭제
        delete_files_query = "DELETE FROM File WHERE board_id = %s"
        cursor.execute(delete_files_query, (board_id,))

        # 게시글 삭제
        delete_board_query = "DELETE FROM Board WHERE board_id = %s"
        cursor.execute(delete_board_query, (board_id,))

        db.commit()
        return jsonify({"message": "게시글이 성공적으로 삭제되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "게시글 삭제 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 게시글 수정 API
@app.route('/board/<int:board_id>/update', methods=['PATCH', 'OPTIONS'])
def update_board(board_id):
    if request.method == 'OPTIONS':
        return jsonify({"message": "CORS preflight success"}), 200
    print("Received board_id:", board_id)
    data = request.json
    print("Request data:", data)
    title = data.get('title')
    content = data.get('content')
    modified_date = datetime.now().strftime('%Y-%m-%d')

    cursor = db.cursor()

    try:
        # 게시글 존재 여부 확인
        check_query = "SELECT * FROM Board WHERE board_id = %s"
        cursor.execute(check_query, (board_id,))
        board = cursor.fetchone()

        if not board:
            return jsonify({"message": "게시글을 찾을 수 없습니다."}), 404

        # 게시글 수정
        update_query = """
            UPDATE Board 
            SET title = %s, content = %s, modifiedDate = %s 
            WHERE board_id = %s
        """
        cursor.execute(update_query, (title, content, modified_date, board_id))
        db.commit()

        return jsonify({"message": "게시글이 성공적으로 수정되었습니다.", "boardId": board_id}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "게시글 수정 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 댓글 목록 가져오기 API
@app.route('/board/<int:board_id>/comment/list', methods=['GET'])
def get_comment_list(board_id):
    try:
        # 페이지 번호와 크기 가져오기 (기본값: 페이지 번호 0, 크기 5)
        page = int(request.args.get('page', 0))
        page_size = int(request.args.get('pageSize', 5))
        offset = page * page_size  # OFFSET 계산

        cursor = db.cursor(dictionary=True)

        # 댓글 목록 조회 쿼리
        query = """
            SELECT 
                c.comment_id AS id,
                c.content,
                c.createdDate,
                c.modifiedDate,
                m.username AS writer
            FROM Comment c
            LEFT JOIN Member m ON c.user_id = m.id
            WHERE c.board_id = %s
            ORDER BY c.createdDate DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (board_id, page_size, offset))
        comments = cursor.fetchall()

        # 댓글 총 개수 조회
        count_query = "SELECT COUNT(*) AS totalElements FROM Comment WHERE board_id = %s"
        cursor.execute(count_query, (board_id,))
        total_elements = cursor.fetchone()["totalElements"]

        cursor.close()

        # 전체 페이지 수 계산
        total_pages = (total_elements + page_size - 1) // page_size

        # 응답 데이터 생성
        response = {
            "content": comments,
            "pageSize": page_size,
            "totalPages": total_pages,
            "totalElements": total_elements
        }

        return jsonify(response), 200
    except mysql.connector.Error as e:
        print("Database error:", str(e))  # 콘솔에 에러 메시지 출력
        return jsonify({"message": "Database error", "error": str(e)}), 500
    except Exception as e:
        print("Unknown error:", str(e))  # 콘솔에 에러 메시지 출력
        return jsonify({"message": "Unknown error", "error": str(e)}), 500


# 댓글 작성 API
@app.route('/board/<int:board_id>/comment/write', methods=['POST'])
def write_comment(board_id):
    data = request.json
    content = data.get('content')  # 댓글 내용
    user_id = request.headers.get('User-ID')  # 사용자 ID (헤더에서 가져옴)
    created_date = datetime.now().strftime('%Y-%m-%d')  # 현재 시간
    modifiedDate = datetime.now().strftime('%Y-%m-%d')  # 현재 시간

    if not user_id:
        return jsonify({"message": "User ID is required"}), 400  # 사용자 ID가 없으면 에러 반환

    cursor = None

    try:
        cursor = db.cursor()
        # 댓글 데이터 삽입 쿼리
        query = """
            INSERT INTO Comment (board_id, user_id, content, createdDate, modifiedDate)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (board_id, user_id, content, created_date, modifiedDate))
        db.commit()

        return jsonify({"message": "댓글이 성공적으로 등록되었습니다."}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": "댓글 등록 중 오류 발생", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()

# 댓글 수정 API (토큰 없이 auth.email로 판단)
@app.route('/board/<int:board_id>/comment/update/<int:comment_id>', methods=['PATCH'])
def update_comment(board_id, comment_id):
    data = request.json
    content = data.get('content')  # 수정할 댓글 내용
    user_email = data.get('user_email')  # 클라이언트에서 보낸 사용자 이메일

    cursor = db.cursor(dictionary=True)
    try:
        # 댓글 작성자 확인
        cursor.execute("SELECT user_id FROM Comment WHERE comment_id = %s", (comment_id,))
        comment = cursor.fetchone()

        if not comment:
            return jsonify({"message": "댓글을 찾을 수 없습니다."}), 404

        if comment["user_id"] != user_email:
            return jsonify({"message": "댓글 수정 권한이 없습니다."}), 403

        # 댓글 수정
        query = "UPDATE Comment SET content = %s, modifiedDate = NOW() WHERE comment_id = %s"
        cursor.execute(query, (content, comment_id))
        db.commit()

        return jsonify({"message": "댓글이 성공적으로 수정되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "댓글 수정 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()



# 댓글 삭제 API (토큰 없이 auth.email로 판단)
@app.route('/board/<int:board_id>/comment/delete/<int:comment_id>', methods=['DELETE'])
def delete_comment(board_id, comment_id):
    data = request.json
    user_email = data.get('user_email')  # 클라이언트에서 보낸 사용자 이메일

    cursor = db.cursor(dictionary=True)
    try:
        # 댓글 작성자 확인
        cursor.execute("SELECT commentWriterName FROM Comment WHERE comment_id = %s", (comment_id,))
        comment = cursor.fetchone()

        if not comment:
            return jsonify({"message": "댓글을 찾을 수 없습니다."}), 404

        if comment["commentWriterName"] != user_email:
            return jsonify({"message": "댓글 삭제 권한이 없습니다."}), 403

        # 댓글 삭제
        query = "DELETE FROM Comment WHERE comment_id = %s"
        cursor.execute(query, (comment_id,))
        db.commit()

        return jsonify({"message": "댓글이 성공적으로 삭제되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "댓글 삭제 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 회원정보 수정시 비밀번호 확인 API
@app.route('/member/verify-password', methods=['POST'])
def verify_password():
    data = request.json
    email = data.get('email')  # 클라이언트에서 전송한 이메일
    password = data.get('password')  # 클라이언트에서 전송한 비밀번호

    cursor = db.cursor(dictionary=True)
    try:
        query = "SELECT * FROM Member WHERE email = %s AND password = %s"
        cursor.execute(query, (email, password))
        user = cursor.fetchone()

        if user:
            return jsonify({"success": True, "message": "비밀번호가 일치합니다."}), 200
        else:
            return jsonify({"success": False, "message": "비밀번호가 일치하지 않습니다."}), 401
    except Exception as e:
        return jsonify({"success": False, "message": "비밀번호 확인 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 회원정보 수정시 사용자 이름 변경 API
@app.route('/member/update-username', methods=['PATCH'])
def update_username():
    data = request.json
    email = data.get('email')  # 클라이언트에서 전송한 이메일
    new_username = data.get('username')  # 변경할 사용자명

    cursor = db.cursor()
    try:
        query = "UPDATE Member SET username = %s, modifiedDate = %s WHERE email = %s"
        modified_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(query, (new_username, modified_date, email))
        db.commit()

        return jsonify({"success": True, "message": "사용자명이 성공적으로 변경되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": "사용자명 변경 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 회원 탈퇴 API
@app.route('/member/delete', methods=['DELETE'])
def delete_member():
    data = request.json
    email = data.get('email')  # 클라이언트에서 전송한 이메일

    cursor = db.cursor()
    try:
        # 회원 삭제
        delete_query = "DELETE FROM Member WHERE email = %s"
        cursor.execute(delete_query, (email,))
        db.commit()

        return jsonify({"success": True, "message": "회원 탈퇴가 성공적으로 처리되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": "회원 탈퇴 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()

# 파일 다운로드
@app.route('/uploads/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"message": "File not found"}), 404

# 파일 삭제
@app.route('/board/<int:board_id>/file/delete', methods=['DELETE'])
def delete_file(board_id):
    file_id = request.args.get('fileId')
    cursor = db.cursor(dictionary=True)

    try:
        # 파일 경로 가져오기
        query = "SELECT filePath FROM File WHERE file_id = %s AND board_id = %s"
        cursor.execute(query, (file_id, board_id))
        file = cursor.fetchone()

        if not file:
            return jsonify({"message": "파일을 찾을 수 없습니다."}), 404

        file_path = file['filePath']
        if os.path.exists(file_path):
            os.remove(file_path)  # 파일 삭제

        # 파일 데이터베이스에서 삭제
        delete_query = "DELETE FROM File WHERE file_id = %s"
        cursor.execute(delete_query, (file_id,))
        db.commit()

        return jsonify({"message": "파일이 삭제되었습니다."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": "파일 삭제 중 오류 발생", "error": str(e)}), 500
    finally:
        cursor.close()



if __name__ == "__main__":
    app.run(debug=True)

    