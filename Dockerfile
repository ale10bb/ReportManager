FROM python:3.9-slim

# set TZ to Asia/Shanghai by default
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# environments for RM
WORKDIR /ReportManager
RUN mkdir storage storage/archive storage/temp && touch storage/RM.log
VOLUME [ "/ReportManager/storage" ]

# requirements for RM
RUN apt-get update && apt-get install -y curl unar && \
    curl -o rarlinux-x64-612.tar.gz https://www.rarlab.com/rar/rarlinux-x64-612.tar.gz && \
    tar -xf rarlinux-x64-612.tar.gz -C /opt && rm rarlinux-x64-612.tar.gz && \
    curl -o /etc/rarreg.key https://gist.githubusercontent.com/MuhammadSaim/de84d1ca59952cf1efaa8c061aab81a1/raw/ca31cbda01412e85949810d52d03573af281f826/rarreg.key && \
    ln -s /opt/rar/unrar /usr/bin/unrar && ln -s /opt/rar/rar /usr/bin/rar && \
    apt-get autoremove -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Flask gunicorn[gevent] zmail walkdir python-docx mysql-connector-python DBUtils DingtalkChatbot chinesecalendar && \
    sed -i "/self.server.login(self.username, self.password)/i\        self.server.ehlo('ReportManager')\n        if self.host == 'shtec.org.cn':\n            self.server.esmtp_features['auth'] = 'LOGIN'" /usr/local/lib/python*/site-packages/zmail/server.py
COPY RM RM
COPY minimal_web.py minimal_web.py
COPY template template

COPY res/docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD [ "main" ]