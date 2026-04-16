import sqlite3

DEFAULT_ON_STATE = 0

def getDefaultDBData(table_name):
    if table_name=="protocol":
        return [
            {"name": proto} for proto in [
                "CIFS", "NFS", "iSCSI-Chap", "iSCSI-NoChap", "FTP",
                "FC", "S3 Object Storage", "iSER-Chap", "iSER-NoChap", "NFS-RDMA"
            ]
        ]
    elif table_name=="vm_profile":
        return [
            {'name': 'Standard', 'vcpu': 1, 'memory': 0.5, 'storage': 10},
            {'name': 'Professional', 'vcpu': 2, 'memory': 1, 'storage': 100},
            {'name': 'Business', 'vcpu': 4, 'memory': 2, 'storage': 500},
            {'name': 'Ultimate', 'vcpu': 8, 'memory': 4, 'storage': 1000}
        ]

    elif table_name=="vm_group":
        return [{"group_name":name,"path_group_icon":path} for name,path in 
                    [("Finance","/images/finance.png"),
                    ("Collaborative", "/images/banking.png"),
                    ("Dental", "/images/dental.png"),
                    ("Digital Signage", "/images/DigitalSignage.png"),
                    ("Education", "/images/education.png"),
                    ("Health", "/images/health.png"),
                    ("Legal", "/images/legal.png"),
                    ("Point of Sale", "/images/point-of-sale.png"),
                    ("Microsoft", "/images/Operating-System.png"),
                    ("Operating System", "/images/Operating-System-2.png"),
                    ("NAS", "/images/nas.png"),
                    ("Restaurant", "/images/Restaurant.png"),
                    ("Surveillance", "/images/Surveillance.png"),
                    ("VDI", "/images/VDI.png"),
                    ("VOIP", "/images/VOIP.png"),
                    ("My Backups", "/images/VOIP.png"),
                    ("Storage Related", "/images/VOIP.png"),
                    ("Docker",  "/images/Docker.png")]]
        
    elif table_name=="vm_image" : 
        return[
            {
                'image_name': 'ubuntu1', 'vm_image_size': 23720160, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu1'
            }, 
            {
                'image_name': 'ubuntu2', 'vm_image_size': 13267968, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Education', 'image_type': 'img', 'file_name': 'Edu12MB'
            }, 
            {
                'image_name': 'ubuntu3', 'vm_image_size': 23720160, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu3'
            }, 
            {
                'image_name': 'Group Office', 'vm_image_size': 0, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 20, 'image_description': 'Group-Office is an enterprise CRM and groupware tool. Share projects, calendars, files and e-mail online with co-workers and clients. Easy to use and fully customizable.', 'path_image_icon': '/images/GroupOffice.png', 'app_download_server': '/Collaborative', 'image_type': 'iso', 'file_name': 'col1'
            }, 
            {
                'image_name': 'Kune', 'vm_image_size': 0, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Kune provides, to each person or collective, a collection of web tools which allows them to boost their potential social actions.', 'path_image_icon': '/images/Kune.png', 'app_download_server': '/Collaborative', 'image_type': 'iso', 'file_name': 'col2'
            }, 
            {
                'image_name': 'Open Project', 'vm_image_size': 10060722, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'OpenProject is the leading open source project management software to support your project management process (PMI)', 'path_image_icon': '/images/OpenProject.png', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'Retro Share', 'vm_image_size': 13267968, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Retroshare creates encrypted connections to your friends. Nobody can spy on you. Retroshare is completely decentralized. This means there are no central servers. It is entirely Open-Source and free. There are no costs, no ads and no Terms of Service.', 'path_image_icon': '/images/RetroShare.jpg', 'app_download_server': '/Education', 'image_type': 'img', 'file_name': 'Edu12MB'
            }, 
            {
                'image_name': 'Project.net', 'vm_image_size': 0, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Project.net is a complete, open source cloud based enterprise project management application that helps companies plan, execute and deliver on their entire portfolio of projects.', 'path_image_icon': '/images/Project_net.jpg', 'app_download_server': '/Collaborative', 'image_type': 'iso', 'file_name': 'col5'
            }, 
            {
                'image_name': 'Zentyal', 'vm_image_size': 10060722, 'vm_group_id': 2, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Zentyal is an open source email and groupware solution based on Ubuntu Linux.', 'path_image_icon': '/images/Zentyal.png', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu4', 'vm_image_size': 0, 'vm_group_id': 3, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu1'
            }, 
            {
                'image_name': 'ubuntu5', 'vm_image_size': 13267968, 'vm_group_id': 3, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Education', 'image_type': 'img', 'file_name': 'Edu12MB'
            }, 
            {
                'image_name': 'ubuntu6', 'vm_image_size': 0, 'vm_group_id': 3, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu7', 'vm_image_size': 497424, 'vm_group_id': 4, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu8', 'vm_image_size': 0, 'vm_group_id': 4, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Digital', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu9', 'vm_image_size': 10060722, 'vm_group_id': 4, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu10', 'vm_image_size': 0, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'ubuntu1'
            }, 
            {
                'image_name': 'ubuntu11', 'vm_image_size': 10060722, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu12', 'vm_image_size': 0, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu13', 'vm_image_size': 0, 'vm_group_id': 6, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu14', 'vm_image_size': 23720160, 'vm_group_id': 6, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu15', 'vm_image_size': 13267968, 'vm_group_id': 6, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Education', 'image_type': 'img', 'file_name': 'Edu12MB'
            }, 
            {
                'image_name': 'ubuntu16', 'vm_image_size': 0, 'vm_group_id': 7, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu17', 'vm_image_size': 23720160, 'vm_group_id': 7, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu18', 'vm_image_size': 0, 'vm_group_id': 7, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu19', 'vm_image_size': 10060722, 'vm_group_id': 8, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu20', 'vm_image_size': 23720160, 'vm_group_id': 8, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu21', 'vm_image_size': 497424, 'vm_group_id': 8, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu22', 'vm_image_size': 23720160, 'vm_group_id': 9, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Microsoft', 'image_type': 'doc', 'file_name': 'ubuntu29'
            }, 
            {
                'image_name': 'ubuntu23', 'vm_image_size': 23720160, 'vm_group_id': 9, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Microsoft', 'image_type': 'doc', 'file_name': 'ubuntu28'
            }, 
            {
                'image_name': 'powerPoint', 'vm_image_size': 10060722, 'vm_group_id': 9, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu25', 'vm_image_size': 10060722, 'vm_group_id': 10, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu26', 'vm_image_size': 0, 'vm_group_id': 10, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu27', 'vm_image_size': 497424, 'vm_group_id': 10, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu28', 'vm_image_size': 23720160, 'vm_group_id': 11, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu29', 'vm_image_size': 10060722, 'vm_group_id': 11, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu30', 'vm_image_size': 0, 'vm_group_id': 11, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu31', 'vm_image_size': 23720160, 'vm_group_id': 12, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu32', 'vm_image_size': 497424, 'vm_group_id': 12, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu33', 'vm_image_size': 497424, 'vm_group_id': 12, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu34', 'vm_image_size': 23720160, 'vm_group_id': 13, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu35', 'vm_image_size': 497424, 'vm_group_id': 13, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu5.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu36', 'vm_image_size': 0, 'vm_group_id': 13, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/Dental', 'image_type': 'iso', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu37', 'vm_image_size': 10060722, 'vm_group_id': 14, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Digital', 'image_type': 'cab', 'file_name': 'digitalDocs'
            }, 
            {
                'image_name': 'ubuntu38', 'vm_image_size': 497424, 'vm_group_id': 14, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Microsoft', 'image_type': 'sys', 'file_name': 'e1k62x64'
            }, 
            {
                'image_name': 'ubuntu39', 'vm_image_size': 23720160, 'vm_group_id': 14, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu4.jpg', 'app_download_server': '/Finance', 'image_type': 'exe', 'file_name': 'ubuntu2'
            }, 
            {
                'image_name': 'ubuntu40', 'vm_image_size': 23720160, 'vm_group_id': 15, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu1.jpg', 'app_download_server': '/VOIP', 'image_type': 'exe', 'file_name': 'ubuntu40'
            }, 
            {
                'image_name': 'ubuntu41', 'vm_image_size': 13267968, 'vm_group_id': 15, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu2.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'Edu12MB'
            }, 
            {
                'image_name': 'ubuntu42', 'vm_image_size': 23720160, 'vm_group_id': 15, 'downloded': 'no', 'image_cost': 100, 'support_cost': 20, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/VOIP', 'image_type': 'exe', 'file_name': 'ubuntu42'
            }, 
            {
                'image_name': 'Moodle', 'vm_image_size': 13267968, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/moodle.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'moodle'
            }, 
            {
                'image_name': 'Canvas', 'vm_image_size': 13267968, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Canvas.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'Canvas'
            }, 
            {
                'image_name': 'OpenSiS', 'vm_image_size': 13267968, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Is a cloud-based student information system developed by OS4ED, a U.S.-based company established in 2008. It serves various educational institutions, including K-12 schools, higher education institutions, trade schools, and virtual learning environments.', 'path_image_icon': '/images/OpenSiS.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'OpenSiS'
            }, 
            {
                'image_name': 'Gibbon', 'vm_image_size': 13267968, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Gibbon.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'Gibbon'
            }, 
            {
                'image_name': 'Fedena', 'vm_image_size': 13267968, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Fedena.jpg', 'app_download_server': '/Education', 'image_type': 'iso', 'file_name': 'Fedena'
            }, 
            {
                'image_name': 'OFBiz', 'vm_image_size': 13267968, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/OFBiz.jpg', 'app_download_server': '/Finance', 'image_type': 'iso', 'file_name': 'OFBiz'
            }, 
            {
                'image_name': 'FrontAccounting', 'vm_image_size': 13267968, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/FrontAccounting.jpg', 'app_download_server': '/Finance', 'image_type': 'iso', 'file_name': 'FrontAccounting'
            }, 
            {
                'image_name': 'Multiview', 'vm_image_size': 13267968, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Multiview.jpg', 'app_download_server': '/Finance', 'image_type': 'iso', 'file_name': 'Multiview'
            }, 
            {
                'image_name': 'Budget Maestro', 'vm_image_size': 13267968, 'vm_group_id': 1, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Budget-Maestro.jpg', 'app_download_server': '/Finance', 'image_type': 'iso', 'file_name': 'Budget-Maestro'
            }, 
            {
                'image_name': 'FlexVDI', 'vm_image_size': 13267968, 'vm_group_id': 14, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/FlexVDI.jpg', 'app_download_server': '/VDI', 'image_type': 'iso', 'file_name': 'FlexVDI'
            }, 
            {
                'image_name': 'Xibo', 'vm_image_size': 13267968, 'vm_group_id': 4, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Xibo.jpg', 'app_download_server': '/Digital', 'image_type': 'iso', 'file_name': 'Xibo'
            }, 
            {
                'image_name': 'iSPY', 'vm_image_size': 13267968, 'vm_group_id': 13, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/iSPY.jpg', 'app_download_server': '/Surveillance', 'image_type': 'iso', 'file_name': 'iSPY'
            }, 
            {
                'image_name': 'Cassandra', 'vm_image_size': 13267968, 'vm_group_id': 17, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Cassandra.jpg', 'app_download_server': '/StorageRelated', 'image_type': 'iso', 'file_name': 'Cassandra'
            }, 
            {
                'image_name': 'simple-web', 'vm_image_size': 945815552, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/simpleWeb.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'simple-web-master'
            }, 
            {
                'image_name': 'cassandra', 'vm_image_size': 548405248, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Cassandra.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'cassandra'
            }, 
            {
                'image_name': 'datadoghq-agent', 'vm_image_size': 487587840, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Datadoghq.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'datadoghq-agent'
            }, 
            {
                'image_name': 'minio', 'vm_image_size': 64906854, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Minio.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'minio'
            }, 
            {
                'image_name': 'odoo', 'vm_image_size': 1095216660, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Odoo.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'odoo'
            }, 
            {
                'image_name': 'redmine', 'vm_image_size': 583008256, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Redmine.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'redmine'
            }, 
            {
                'image_name': 'suitecrm', 'vm_image_size': 979369984, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/Suitecrm.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'suitecrm'
            }, 
            {
                'image_name': 'fedena', 'vm_image_size': 593494016, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'username: admin Password: admin123', 'path_image_icon': '/images/Fedena.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'fedena'
            }, 
            {
                'image_name': 'opensis', 'vm_image_size': 859832320, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Admin-Username: adminAdmin-Password: admin', 'path_image_icon': '/images/OpenSiS.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'opensis'
            }, 
            {
                'image_name': 'moodle', 'vm_image_size': 1245540515, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Moodle is the world’s most customizable and trusted eLearning solution that empowers educators to improve our world. Today, hundreds of millions of people in thousands of educational institutions and organizations around the globe use Moodle as a toolbox to manage their online learning.', 'path_image_icon': '/images/moodle.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'moodle'
            }, 
            {
                'image_name': 'AutoCAD', 'vm_image_size': 1245540515, 'vm_group_id': 5, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/AutoCAD.jpg', 'app_download_server': '/Education', 'image_type': 'exe', 'file_name': 'AutoCAD'
            }, 
            {
                'image_name': 'sanuyi-dvr', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/sanuyiDVR.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'sanuyi-dvr'
            },
            {
                'image_name': 'ubuntu-os', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'Ubuntu-OS'
            },
            {
                'image_name': 'ubuntu-os-ssh', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'DESCRIPTION SHOULD BE DISPLAYED HERE', 'path_image_icon': '/images/ubuntu3.jpg', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'Ubuntu-OS-ssh'
            },
            {
                'image_name': 'jellyfin', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Is the volunteer-built media solution that puts you in control of your media. Stream to any device from your own server, with no strings attached. Your media, your server, your way.', 'path_image_icon': '/images/jellyfin_docker.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'jellyfin'
            },
            {
                'image_name': 'portainer', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Manage container images, IaC files, Helm charts and more in a single system, providing unrivaled visibility into your development organization and a single source of truth.', 'path_image_icon': '/images/portainer_docker.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'portainer'
            },
            {
                'image_name': 'elastisearch', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industrys standard dummy text ever since the 1500s....', 'path_image_icon': '/images/Elastisearch.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'elasticsearch'
            },
            {
                'image_name': 'solr', 'vm_image_size': 261095424, 'vm_group_id': 18, 'downloded': 'no', 'image_cost': 'free', 'support_cost': 10, 'image_description': 'Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industrys standard dummy text ever since the 1500s....', 'path_image_icon': '/images/solr_docker.png', 'app_download_server': '/Docker', 'image_type': 'zip', 'file_name': 'solr'
            }
        ]


def Insert_Into_Table(conn, table_name, data_dict):
    try:
        c = conn.cursor()
        columns = ', '.join(data_dict.keys())
        placeholders = ', '.join(['?' for _ in data_dict.values()])
        query = f'INSERT INTO {table_name} ({columns}, cr_date, edit_date) VALUES ({placeholders}, datetime(), datetime())'
        c.execute(query, tuple(data_dict.values()))
    except Exception as e:
        print(f"Insert_Into_Table Error: {e}")
        raise  # re-raise so caller can handle or rollback

def Create_Only_If_Empty(dbFileName, table_name, data_list):
    try:
        with sqlite3.connect(dbFileName) as conn:
            conn.text_factory = str
            c = conn.cursor()

            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = c.fetchone()[0]

            if count == 0:
                for entry in data_list:
                    Insert_Into_Table(conn, table_name, entry)
                print(f"{table_name} table populated with default records.")

            conn.commit()
    except Exception as e:
        print(f"Create_Only_If_Empty Error [{table_name}]: {e}")


def Create_Update_VMImage(dbFileName):
    vm_images = getDefaultDBData("vm_image")#["vm_image"]

    try:
        with sqlite3.connect(dbFileName) as conn:
            conn.text_factory = str
            c = conn.cursor()

            for image in vm_images:
                image_name = image["image_name"]
                
                # Check if image already exists
                c.execute("SELECT 1 FROM vm_image WHERE image_name = ?", (image_name,))
                result = c.fetchone()

                if not result:
                    Insert_Into_Table(conn, "vm_image", image)
                    print(f"Inserted VM image: {image_name}")

            conn.commit()

    except Exception as e:
        print(f"Create_Update_VMImage Error: {e}")


def fetch_tables(dbFileName):
    tables = []
    conn = sqlite3.connect(dbFileName)
    c = conn.cursor()
    db_open  = True
    try:
        c = conn.execute("select name from sqlite_master where type = 'table' ")
        for col in c:
            if col[0]!="sqlite_sequence":
                tables.append(col[0])
        c.close()
        conn.close()
        db_open = False
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        
    return tables
    
def default_data(dbFileName):
    print("defailt_data",dbFileName)
    updatable = {}
    insert_only = {}
    if dbFileName=="sdsDB.db" or dbFileName.endswith("sdsDB.db"):
        insert_only={"protocol": getDefaultDBData("protocol")}
    
    for key, func in updatable.items():
        print(f"{key}:{func}")
        try:
            func(dbFileName)
            
        except Exception as e:
            print(e)
        print()

    for table_name, records in insert_only.items():
        try:
            Create_Only_If_Empty(dbFileName, table_name, records)

        except Exception as e:
            print(e)


