import os
import socket

class Parser:
    content_types = [
            'text/html',
            'text/plain',
            'image/jpeg',
            'image/png',
            'multipart/form-data'
        ]
    REQUESTS = [
        'GET',
        'POST',
        'PUT',
        'DELETE',
        'HEAD'
    ]

    @staticmethod
    def parse_http(msg, COOKIES):
        status = 200 # default OK
        # split by the first '\r\n\r\n'
        header, body = msg.split(b'\r\n\r\n', 1)

        # parse header
        header_list = (header.decode('utf-8')).split('\r\n')
        header_dict = {
            'request_method': None,
            'request_page': None,
            'http_version': None,
            'Content-Type': None,
            'boundary': None,
            'User-Agent': None,
            'Accept': None,
            'Postman-Token': None,
            'Host': None,
            'Accept-Encoding': None,
            'Connection': None,
            'Content-Length': None,
            'Cookie_name': None,
            'Cookie_value': None,
            'Cache-Control': None,
            'Referer': None
        }
        for h in header_list:
            if ' HTTP/' in h:
                header_dict['request_method'], header_dict['request_page'], header_dict['http_version'] = h.split()
                if header_dict['request_page'] == '/':
                    header_dict['request_page'] = '/index.html'
                elif header_dict['request_page'] == '/old_index.html': # mock redirect from '/old_index.html' to '/index.html'
                    header_dict['request_page'] = '/index.html'
                    status = 301
                # detect errors
                if header_dict['http_version'] != 'HTTP/1.1': # verify http version
                    print('Unsupported HTTP version!')
                    raise ValueError(505, header_dict)
                if header_dict['request_method'] not in Parser.REQUESTS: # not implemented request tyeps
                    print('Unimplemented method!')
                    raise ValueError(400, header_dict)
            elif 'Content-Type' in h:
                if 'multipart/form-data' in h:
                    header_dict['Content-Type'] = 'multipart/form-data'
                    header_dict['boundary'] = '--' + h.replace('Content-Type: multipart/form-data; boundary=', '')
                else:
                    header_dict['Content-Type'] = h.replace('Content-Type: ', '')
            elif 'User-Agent' in h:
                header_dict['User-Agent'] = h.replace('User-Agent: ', '')
            elif 'Accept' in h:
                if 'Accept-Encoding' in h:
                    header_dict['Accept-Encoding'] = h.replace('Accept-Encoding: ', '')
                else:
                    header_dict['Accept'] = h.replace('Accept: ', '')
            elif 'Postman-Token' in h:
                header_dict['Postman-Token'] = h.replace('Postman-Token: ', '')
            elif 'Host' in h:
                header_dict['Host'] = h.replace('Host: ', '')
            elif 'Connection' in h:
                header_dict['Connection'] = h.replace('Connection: ', '')
            elif 'Content-Length' in h:
                header_dict['Content-Length'] = h.replace('Content-Length: ', '')
            elif 'Cache-Control' in h:
                header_dict['Cache-Control'] = h.replace('Cache-Control: ', '')
            elif 'Referer' in h:
                header_dict['Referer'] = h.replace('Referer: ', '')
            elif 'Cookie' in h:
                header_dict['Cookie_name'], header_dict['Cookie_value'] = (h.replace('Cookie: ', '')).split('=')
                temp_cookie = bytes(header_dict['Cookie_value'].encode('utf-8'))
                if (temp_cookie not in COOKIES) or temp_cookie == None: # verify cookie
                    print('Unauthenticated cookie!')
                    raise ValueError(401, header_dict)
            else: # other keys not in scpoe
                pass
        header_dict = {key: value.encode('utf-8') if isinstance(value, str) else value for key, value in header_dict.items()} # value from str to bytes

        # parse body
        body_dict = {
            'Content-Disposition': None,
            'name': None,
            'filename': None,
            'Content-Type': None,
            'Content': None
        }
        if header_dict['Content-Type'] == b'multipart/form-data':
            body_dict['Content-Disposition'] = b'form-data'
            body = body[(body.find(b'\r\n')) + 2:(body.rfind(b'\r\n', 0, -2))] # get content between first and second last index
            temp, body_dict['Content'] = body.split(b'\r\n\r\n', 1)
            temp = temp.replace(b'Content-Disposition: form-data; name="', b'')
            body_dict['name'], temp = temp.split(b'"; filename="')
            body_dict['filename'], body_dict['Content-Type'] = temp.split(b'"\r\nContent-Type: ')
        else:
            body_dict['Content'] = body
            
        # finish
        return status, header_dict, body_dict # type(key) = str, type(value) = bytes

class Server:
    def __init__(self):
        self.STATUS = {
            200: 'OK',
            301: 'Moved Permanently',
            400: 'Bad Request',
            401: 'Unauthorized',
            404: 'Not Found',
            505: 'HTTP Version Not Supported'
        }
        self.COOKIES = [
            b'cookie1',
            b'cookie2',
            b'cookie3',
            b'cookie4',
            b'cookie5'
        ]
        self.HOST = 'localhost'
        self.PORT = 8080
        self.status = None
        self.response = None
    
    def build_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.HOST, self.PORT)) # bind socket to ip
        self.socket.listen(1) # listen request
    
    def listen_http_request(self):
        self.connection, self.address = self.socket.accept()
        self.connection.settimeout(0.1) # set timeout = 0.1s
        self.msg = b''
        while True:
            try:
                fragment = self.connection.recv(1024)
                if fragment:
                    self.msg += fragment
                else:
                    break
            except socket.timeout: # if didn't receive data in 0.1s, previous data is the last fragment
                break
    
    def mock_http_version_error(self):
        self.msg = self.msg.replace(b'HTTP/1.1', b'HTTP/1.0', 1)
    
    def parse_http(self):
        try: # correct status: 200/301
            self.status, self.header, self.body = Parser.parse_http(self.msg, self.COOKIES)
            self.response = self.header['http_version'].decode('utf-8') + f' {self.status} ' + self.STATUS[self.status]
        except ValueError as e: # parse error status: 400/401/505
            self.status, self.header = e.args
            self.response = self.header['http_version'] + f' {self.status} {self.STATUS[self.status]}\n\n'
            self.header = {key: value.encode('utf-8') if isinstance(value, str) else value for key, value in self.header.items()}

    def operate(self):
        if '301' in self.response:
            # send 301 response and close connection
            self.response += '\r\nLocation: /index.html\r\n\r\n'
            print('{} request accepted. Redirecting to index.html...'.format(self.header['request_method'].decode()))
        if '200' in self.response:
            try:
                # check is support filetype
                if self.header['Content-Type'] == b'multipart/form-data': # raw file
                    filetype = self.body['Content-Type'].decode('utf-8')
                else:
                    if self.header['Content-Type'] == None: # judge by the request page
                        _, filetype = (self.header['request_page'].decode('utf-8')).rsplit('.', 1)
                        if 'html' in filetype:
                            filetype = 'text/html'
                        elif 'txt' in filetype:
                            filetype = 'text/plain'
                        elif 'jpeg' in filetype:
                            filetype = 'image/jpeg'
                        elif 'png' in filetype:
                            filetype = 'image/png'
                        else:
                            raise ValueError # 400
                    else: # if support in header
                        filetype = self.header['Content-Type'].decode('utf-8')
                        if filetype not in Parser.content_types:
                            raise ValueError # 400

                # operate
                try:
                    self.response += ('\r\nContent-Type: ' + filetype + '\r\nSet-Cookie: ' + self.header['Cookie_name'].decode('utf-8') + '=' + self.header['Cookie_value'].decode('utf-8') + '; Secure; HttpOnly') # please remove Set-Cookie
                    filepath = os.path.join(os.getcwd(), self.header['request_page'].decode('utf-8')[1:])
                    match(self.header['request_method']):
                        case b'HEAD': # use 'none' mode
                            self.response += '\r\n\r\n'
                            print('HEAD request accepted.')
                        case b'GET': # use 'none' mode
                            with open(filepath, 'r') as file:
                                self.response += ('\r\n\r\n' + file.read())
                            print('GET request accepted.')
                        case b'POST': # use 'raw' mode and choose 'text' to append content(txt)
                            if os.path.exists(filepath):
                                self.response += '\r\n\r\nFile already exist (409 Error)'
                            else:
                                with open(filepath, 'wb') as file:
                                    file.write(self.body['Content'])
                                self.response += '\r\n\r\nFile created'
                            print('POST request accepted.')
                        case b'PUT': # use 'form-data' mode to upload file(txt/html/png/jpeg)
                            with open(os.path.join(os.getcwd(), self.body['filename'].decode('utf-8')), 'wb') as file:
                                file.write(self.body['Content'])
                            self.response += '\r\n\r\nFile created/covered'
                            print('PUT request accepted.')
                        case b'DELETE': # use 'none' mode
                            os.remove(filepath)
                            self.response += '\r\n\r\nFile deleted'
                            print('DELETE request accepted.')
                except FileNotFoundError:
                    self.status = 404
                    self.response = self.header['http_version'].decode('utf-8') + f' {self.status} {self.STATUS[self.status]}\n\n'
                    print('File doesn\'t exist!')
            except ValueError: # filetype not txt/html/jpeg/png
                self.status = 400
                self.response = self.header['http_version'].decode('utf-8') + f' {self.status} {self.STATUS[self.status]}\n\n'
                print('Unsupported file type!')
        
        self.connection.sendall(self.response.encode())
        self.connection.close()

def main():
    # init
    server = Server()
    server.build_socket()

    while True:
        # greeting message
        print('> Listening request... ', end = '')
        # get http request
        server.listen_http_request()
        # if want to test 505 error, un-comment the above line -|
        #server.mock_http_version_error() # <-------------------|
        # parse header and body
        server.parse_http()
        # operate by the request
        server.operate()
        
        if server.status != 301:
            #if input('\'Q\' to quit, other key to continue: ') == 'Q':
            #    break
            print()
    #server.socket.close()

main()