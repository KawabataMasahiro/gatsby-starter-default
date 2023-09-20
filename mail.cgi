#!/usr/bin/perl

#====================================================
# 汎用メールフォーム
#====================================================
# このファイルの文字コードはUTF-8N(Character Code : UTF-8N)
#====================================================
# 作成日：2008/07/24
# 作成者：Y.Takiguchi(Onocomm)
# 更新日：2015/05/13
# 更新者：Y.Takiguchi(Onocomm)
#====================================================
# 版 | 日付       | 名前            | 内容
#----------------------------------------------------
# 00 | 2008/07/28 | Y.Takiguchi     | 初版
#----------------------------------------------------
# 01 | 2009/10/14 | Y.Takiguchi     | UTF-8に対応(settings.txtにencmodeを追加。
#                                     encmode=utf8でUTF-8、encmode=shiftjisでSJIS
#                                     settings.txt,names.txtは常にshift-jis。cgi,pl,pmは常にUTF-8。それ以外は利用したい文字コードに合わせる)
#----------------------------------------------------
# 02 | 2013/08/28 | Y.Takiguchi     | ファイルアップロードの複数フィールドに対応
#----------------------------------------------------
# 03 | 2015/05/13 | Y.Takiguchi     | フォーム内にエラーを表示する形に仕様変更。
#                                     メールアドレス項目がある場合は、管理者宛送信時にそのアドレスをFromヘッダとする(envfromはsettings.txt)
#====================================================
# hiddenのnameはmode,tmpfileが予約語。
#----------------------------------------------------
# Perl5.8.8以上対応。
# HTML::Template, base64.pl, 独自モジュールのOCCharが必要
# HTML::Templateがインストールされていない場合は、同じディレクトリに
# モジュールファイルを配置
#----------------------------------------------------
# copyright (c) 2008 ONOCOMM Co.,Ltd. (http://www.onocomm.co.jp/)
#----------------------------------------------------

use strict;
use lib './';
use HTML::Template;

use utf8;	#このファイルはUTF-8(UTF-8N)
use CGI;
#$CGI::LIST_CONTEXT_WARN = 0;
#use Encode qw(from_to encode decode);
#use Encode::Guess;

use OCChar;	#文字列操作用クラス

require './base64.pl';	#base64ライブラリ

##設定項目用変数
#項目用
my @names;
my %names_hash;
my $names_cnt;

#各種設定用
my %set_hash;
my $set_cnt;

#エラーメッセージ格納用
my %error_hash;

#フォーム表示データ格納用
my %formdisp_hash;

my $g_mode="";

my %SETTING = (
	tmpl_form     => "index.html",		#フォームテンプレート
	tmpl_confirm  => "confirm.html",	#確認画面テンプレート
	tmpl_error    => "error.html",		#エラー画面テンプレート
	tmpl_mail     => "mail.txt",		#メールテンプレート
	data_names    => "names.txt",		#項目設定ファイル
	data_settings => "settings.txt",	#各種設定ファイル
);

&fMain();

#=========================#
# エントリポイント
#=========================#
sub fMain{

	my $errbuf="";
	my $q = new CGI;
	my $ret;

	$g_mode = $q->param(&_ENSET("mode"));

	$errbuf = &fGetSettings();	#設定情報取得
	if($errbuf ne ""){
		&fDispLogError($errbuf);
		return;
	}

	$errbuf = &fDelOldTmp;	#古いテンポラリファイルを削除
	if($errbuf ne ""){
		&fDispLogError($errbuf);
		return;
	}

	if($g_mode eq "confirm"){	#確認画面
		&fConfirm($q);
		
	}elsif($g_mode eq "send"){	#メール送信
		&fMailsend($q);
		
	}else{	#インデックスページ
		&fDispIndex($q);
	
#		&fDispLogError("不正なリクエストです");
	}

	return;
}

#=========================#
# メール送信と完了画面
#=========================#
sub fMailsend{

	my $q = shift;
	my $errbuf="";
	my %data;	#データ受け取り用バッファ
	
	my $i;
	my $replymail="";
	my $replymailname="";
	#-------------------------

	#データ取得
	$errbuf = &fGetData($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}
	
	#パラメータチェック
	$errbuf = fCheckParam($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}

	#typeがmailに設定されているデータ(返信先メールアドレス)を探す
	for($i=0;$i<$names_cnt;$i++){
		if($names[$i]{"type"} eq "mail"){
			$replymailname = $names[$i]{"name"};
			$replymail = $data{$replymailname};
			last;
		}
	}
	$replymail =~ s/[\r\n]//gi;	#改行を削除

	#ログ
	$errbuf = &fLogging("[MAIL]before sending.<" . $replymail . ">");
	if($errbuf ne ""){	return;	}

	#メール送信
	$errbuf = &fSendmail($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}

	#ログ
	$errbuf = &fLogging("[MAIL]sent.<" . $replymail . ">");
	if($errbuf ne ""){	return;	}

	#完了画面
	$errbuf = &fDispComplete($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}

	return;

}

#=========================#
# 完了画面
#=========================#
sub fDispComplete{

	my $q = shift;
	my $data = shift;
	
	my $ret;
	#-------------------------
	
	&fPrintHeader(1, $set_hash{"url_complete"});

	return "";
}

#=========================#
# 確定処理
#=========================#
sub fSendmail{

	my $q = shift;
	my $data = shift;
	
	my $errbuf="";
	
	my $bodybuf="";	#メールのBody用
	
	my $i;
	my $ret;
	my $tmpl;
	my $filebuf="";	#BASE64エンコード後
	my %hfilebuf;
	my %hfilename;
	
	my $replymailname="";
	my $filename="";

	my $attachflg=0;

	my $name;
	#-------------------------

	#テンプレート差し込み
	$ret = &fOpenTmpl(\$tmpl, $SETTING{"tmpl_mail"});
	if($ret){	return &fDispLogError("メールテンプレートの読み込みに失敗しました");	}

	eval{
		for($i=0;$i<$names_cnt;$i++){
			$name=$names[$i]{"name"};
			$tmpl->param(&_ENSET($name) => &_ENSET($$data{$name}));
		}

		#送信時間
		$tmpl->param(&_ENSET("sendtime") => &_ENSET(&fDefTime(0,11)));
		
		$bodybuf = $tmpl->output();
		undef $tmpl;
	};
	
	if($@){	return &fDispLogError("メールの作成に失敗しました");	}

	$bodybuf = &_DCSET($bodybuf);	#Sjis状態のものを内部文字形式に戻す

	for($i=1;$i<=$set_hash{"tmpfilecnt"};$i++){
		$filebuf = "";
		my $thashname = "tmpfile" . $i;
		#添付ファイルがあれば、テンポラリファイルをBase64エンコード
		if($$data{$thashname} ne ""){
			
			if($$data{$thashname} =~ m/[^a-zA-Z0-9_\.]/){	return &fDispLogError("不正なパラメータが検出されました");	}

			if(!(-e $set_hash{"tmpfiledir"} . $$data{$thashname})){
				return &fDispLogError("テンポラリファイルが見つかりませんでした。");
			}

			$ret = open(DATA,$set_hash{"tmpfiledir"} . $$data{$thashname});
			if(!$ret){	return &fDispLogError("テンポラリファイルをオープンできませんでした");	}

			my $bytesread;
			my $buffer="";

			while ($bytesread = read(DATA,$buffer,60*57)) {	#細切れにしてエンコード
				$filebuf .= &fEncodeBase64($buffer);
			}

			close(DATA);
			if($filebuf eq ""){	return &fDispLogError("テンポラリファイルをエンコードできませんでした");	}
			$hfilebuf{$thashname} = $filebuf;
			$attachflg=1;
		}
		
	}

	#typeがmailに設定されているデータ(返信先メールアドレス)を探す
	for($i=0;$i<$names_cnt;$i++){
		if($names[$i]{"type"} eq "mail"){
			$replymailname = $names[$i]{"name"};
		}
		if($names[$i]{"type"} eq "file"){
			$filename = $names[$i]{"name"};
			$hfilename{$filename} =  $$data{$filename};
		}
	}
	
	#管理者に送る
	$errbuf = &fMailSending($set_hash{"sendmailpath"}, 
				$set_hash{"to"},	#MailFrom
				$$data{$replymailname} ne "" ? $$data{$replymailname} : $set_hash{"from"},	#From(フォームのメルアドを差出人に)
				$set_hash{"to"}, $set_hash{"cc"}, $set_hash{"bcc"},
				$set_hash{"mailtitle"}, $bodybuf, $attachflg, \%hfilename, \%hfilebuf );
	if($errbuf ne ""){	return $errbuf;	}

	#送り主に返す(自動返信がonの場合のみ)
	if($set_hash{"reply"} eq "on"){
		$errbuf = &fMailSending($set_hash{"sendmailpath"}, 
					$set_hash{"to"},	#MailFrom
					$set_hash{"from"},	#From
					$$data{$replymailname}, "", "",
					$set_hash{"mailtitle"}, $bodybuf, 0, "", "");	#添付ファイルは無し
		if($errbuf ne ""){	return $errbuf;	}
	}

	return "";

}

#=========================#
# メール送信処理
#=========================#
sub fMailSending{

	my $sendmailpath = shift;
	my $mailfrom = shift;
	my $from = shift;
	my $to = shift;
	my $cc = shift;
	my $bcc = shift;
	my $subject = shift;
	my $body = shift;
	my $attachflg = shift;
	my $filename = shift;
	my $attach = shift;	#添付ファイルはメモリを食わないように参照で受け取る
	my $boundary="-*-*-*-*-*-*-*-*-Boundary_" . time . "_" . $$;

	my $i;
	my $mailbuf = "";
	my $num;
	#-------------------------

	if(!defined($filename)){	$filename = "";	}	#未定義の場合は空に
	if(!defined($subject)){		$subject = "";	}	#未定義の場合は空に
	if(!defined($body)){		$body = "";		}	#未定義の場合は空に

	$subject = OCChar->EncodeMIME($subject);
	$body = OCChar->Encode7bitJIS($body);
#	$body = OCChar->EncodeJISMS($body);
	if($attachflg){
		foreach(keys %{$filename}){
			$$filename{$_} = OCChar->EncodeMIME($$filename{$_});
		}
	}

#	if($set_hash{"from"} ne ""){
#		$from = $set_hash{"from"};
#	}

	my $ret;
	
	$ret = open(MAIL, "|" . $sendmailpath . " -i -f " . "\"" . $mailfrom . "\"" . " -t");
	if(!$ret){
		return &fDispLogError("メールの送信に失敗しました。お手数ではございますが、お急ぎの場合は直接お問い合わせ下さい。");
	}

	if($attachflg){
		print MAIL OCChar->EncodeEucJp("MIME-Version: 1.0" . "\n");
		print MAIL OCChar->EncodeEucJp("Content-Type: Multipart/Mixed; boundary=\"" . $boundary ."\"\n");
		print MAIL OCChar->EncodeEucJp("Content-Transfer-Encoding:Base64\n");
	}

	print MAIL OCChar->EncodeEucJp("From: " . $from . "\n");
	print MAIL OCChar->EncodeEucJp("To: " . $to . "\n");
	if($cc  ne ""){	print MAIL OCChar->EncodeEucJp("Cc: "  . $cc  . "\n");	}
	if($bcc ne ""){	print MAIL OCChar->EncodeEucJp("Bcc: " . $bcc . "\n");	}
	print MAIL OCChar->EncodeEucJp("Subject: ") . $subject . OCChar->EncodeEucJp("\n");

	# メール本文のパート
	if($attachflg){
		print MAIL OCChar->EncodeEucJp("--" . $boundary . "\n");
	}
	print MAIL OCChar->EncodeEucJp("Content-Type: text/plain; charset=\"ISO-2022-JP\"\n");
	print MAIL OCChar->EncodeEucJp("\n");
	print MAIL $body . OCChar->EncodeEucJp("\n");

	# 添付ファイルのパート
	for($i=1;$i<=$set_hash{"tmpfilecnt"};$i++){
		
		if($attachflg && $$filename{"file" . $i} ne ""){

			print MAIL "--" . $boundary . "\n";

			print MAIL OCChar->EncodeEucJp("Content-Type: application/octet-stream; name=\"" . $$filename{"file" . $i} . "\"\n");
			print MAIL OCChar->EncodeEucJp("Content-Transfer-Encoding: base64\n");
			print MAIL OCChar->EncodeEucJp("Content-Disposition: attachment; filename=\"" . $$filename{"file" . $i} . "\"\n");
			print MAIL OCChar->EncodeEucJp("\n");
			print MAIL $$attach{"tmpfile" . $i} . OCChar->EncodeEucJp("\n");
			print MAIL OCChar->EncodeEucJp("\n");
		}
	}
	
	if($attachflg){
		# マルチパートのおわり。
		print MAIL OCChar->EncodeEucJp("--" . $boundary . "--\n");
	}

	close(MAIL);
	
	return "";

}

#=========================#
# 確認画面
#=========================#
sub fConfirm{

	my $q = shift;
	my $errbuf="";
	my %data;	#データ受け取り用バッファ
	#-------------------------

	$errbuf = &fGetData($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}
	
	$errbuf = fCheckParam($q, \%data);
	if($errbuf ne ""){
		&fDispIndex($q, \%data);	#エラーの場合はフォームに戻る
#		&fDispError($errbuf);
		return;
	}

	$errbuf = &fDispConfirm($q, \%data);
	if($errbuf ne ""){
		&fDispError($errbuf);
		return;
	}

	return;

}

#=========================#
# フォーム画面
#=========================#
sub fDispIndex{
	my $q = shift;
	my $data = shift;

	my $errbuf="";
	my $tmpl;
	my $ret;
	
	my $i;
	#-------------------------

	#テンプレート差し込み
	$ret = &fOpenTmpl(\$tmpl, $SETTING{"tmpl_form"});
	if($ret){	return &fDispLogError("フォームテンプレートの読み込みに失敗しました");	}

	eval {

		for($i=0;$i<$names_cnt;$i++){
			#複数選択セレクト
			if($names[$i]{"type"} eq "select"){
				my @lst = split(/,/,$$data{$names[$i]{"name"}});
				foreach(@lst){
					$$data{$names[$i]{"name"} . "_" . $_} = $_;
				}
			}
			#ラジオボタン
			if($names[$i]{"type"} eq "radio"){
				$$data{$names[$i]{"name"} . "_" . $$data{$names[$i]{"name"}} } = "checked";
			}
			
			#チェックボックス
			if($names[$i]{"type"} eq "check"){
				my @lst = split(/,/,$$data{$names[$i]{"name"}});
				foreach(@lst){
					$$data{$names[$i]{"name"} . "_" . $_ } = "checked";
				}
			}
		}

# エラーがあった場合は添付ファイルをもう一度アップロードしてもらう
#		for($i=1;$i<=$set_hash{"tmpfilecnt"};$i++){
#			if($$data{"tmpfile" . $i}){	#添付ファイルありの場合
#				$hidden .= &fCreateHidden("tmpfile" . $i, &fHTMLSanitizing($$data{"tmpfile" . $i}));
#			}
#		}

		my $tmp;
		#フォームデータ差し込み
		foreach $tmp (keys %{$data}){
			$tmpl->param(&_ENSET($tmp) => &_ENSET($$data{$tmp}));
		}
		#エラー差し込み
		foreach $tmp (keys %error_hash){
			$tmpl->param(&_ENSET($tmp . "_error") => &_ENSET($error_hash{$tmp}));
		}

	};
	
	if($@){	return &fDispLogError("フォーム画面の作成に失敗しました");	}

	&fPrintHeader(0,"");
	print $tmpl->output();

	undef $tmpl;
	
	return "";
}

#=========================#
# 確認画面表示
#=========================#
sub fDispConfirm{

	my $q = shift;
	my $data = shift;
	
	my $tmpl;
	my $ret;
	my $hidden="";
	
	my $i;
	#-------------------------

	#テンプレート差し込み
	$ret = &fOpenTmpl(\$tmpl, $SETTING{"tmpl_confirm"});
	if($ret){	return &fDispLogError("確認画面テンプレートの読み込みに失敗しました");	}

	eval {

		for($i=0;$i<$names_cnt;$i++){
		
			#値が送られてきていない場合は、空文字を入れておく。
			if(!defined($$data{$names[$i]{"name"}})){	$$data{$names[$i]{"name"}} = "";	}
			
			if($$data{$names[$i]{"name"}} eq "" && $names[$i]{"need"} eq 'need' ){
				$tmpl->param(&_ENSET($names[$i]{"name"}) => &_ENSET("必須項目です"));
			}else{
				#テキストを無害化してから表示
				$tmpl->param(&_ENSET($names[$i]{"name"}) => &_ENSET(&fCRLFtoBR(&fHTMLSanitizing($$data{$names[$i]{"name"}}))));
				$hidden .= &fCreateHidden(&fHTMLSanitizing($names[$i]{"name"}),&fHTMLSanitizing($$data{$names[$i]{"name"}}));
			}
		}

		for($i=1;$i<=$set_hash{"tmpfilecnt"};$i++){
			if($$data{"tmpfile" . $i}){	#添付ファイルありの場合
				$hidden .= &fCreateHidden("tmpfile" . $i, &fHTMLSanitizing($$data{"tmpfile" . $i}));
			}
		}

		#引き継ぎパラメータ
		$tmpl->param(&_ENSET("hidden") => &_ENSET($hidden));

	};
	
	if($@){	return &fDispLogError("確認画面の作成に失敗しました");	}

	&fPrintHeader(0,"");
	print $tmpl->output();

	undef $tmpl;
	
	return "";
}

#=========================#
# データ取得（確認時、送信時共通）
#=========================#
sub fGetData{

	my $q = shift;
	my $data = shift;
	
	my $errbuf="";
	
	my $i;
	my $ret;
	my $totalsize=0;
	
	my $name;

	my $tmpfile="";	#テンポラリファイル名

	my $fcnt=0;	#ファイルカウント用
	#-------------------------

	#データの取得（設定されているデータのみ取得する）
	for($i=0;$i<$names_cnt;$i++){

		$name=$names[$i]{"name"};

		my @list;
		if($CGI::VERSION >= 4.08){	# CGI.pm 4.08以上は、複数データ取得でmulti_param推奨
			@list = $q->multi_param(&_ENSET($name));
		}else{
			@list = $q->param(&_ENSET($name));
		}
		
		$$data{$name} = &_DCSET(join(',',@list));
		
		#確認時(初回送信時)のみファイルの保存を行う
		if($q->param(&_ENSET("mode")) ne "confirm"){	next;	}

		#メールは半角を全角に自動的に直す
		if($names_hash{$name}{"type"} eq "mail"){
			$$data{$name} = &fHankakuToZenkaku($$data{$name});
		}

		#ファイルの場合はテンポラリファイルに書き出す。
		if($names_hash{$name}{"type"} eq "file" && $$data{$name} ne ""){
			$fcnt++;
#			$tmpfile=time . "_" . Digest::MD5::md5_hex(&_ENSET($$data{$name}));
			$tmpfile=time . "_" . $ENV{"REMOTE_ADDR"} . "_" . $fcnt;

			$ret = open(TMP, ">" . $set_hash{"tmpfiledir"} . $tmpfile);
			if(!$ret){
				return &fDispLogError("テンポラリファイルを作成することができませんでした。");
			}
			
			#一時ファイルを格納
			my $bytesread;
			my $buffer="";
			my $handle = $q->param(&_ENSET($name));
			while ($bytesread = read($handle,$buffer,1024)) {
				$totalsize+=$bytesread;
				print TMP $buffer;
				if($totalsize>$set_hash{"max_filesize"}*1000){
					$errbuf = "アップロードしたファイルの容量が大きすぎるため、受け付けできませんでした。" .
					          "約" . $set_hash{"max_filesize"} . "Kバイト以内におさめてください。";
					last;
				}
			}

			close(TMP);
			chmod(0666, $set_hash{"tmpfiledir"} . $tmpfile);	#ReadとWriteを付加

			$$data{$name} = &fGetFilename($$data{$name});
			$$data{"tmpfile" . $fcnt} = $tmpfile;

		}
	}

	#テンポラリファイル名がある場合（確認画面からのsubmit時）
	for($i=1;$i<=$set_hash{"tmpfilecnt"};$i++){
		if($q->param(&_ENSET("tmpfile" . $i)) ne ""){
			$$data{"tmpfile" . $i} = $q->param(&_ENSET("tmpfile" . $i));
		}
	}

	if($errbuf ne ""){	return $errbuf;	}
	
	return "";

}


#=========================#
# パラメータチェック（確認時、送信時共通）
# データは全てチェックして、全てのエラー箇所を報告。
#=========================#
sub fCheckParam{

	my $q = shift;
	my $data = shift;
	
	my $errbuf="";
	
	my $i;
	my $ret;
	my $totalsize=0;
	
	my $name;
	
	my $tmpfile="";	#テンポラリファイル名
	#-------------------------

	for($i=0;$i<$names_cnt;$i++){
	
		$name=$names[$i]{"name"};
		if($names_hash{$name}{"type"} eq "mail"){	#メールの場合はメールアドレスチェック
			if(&fCheckMailAddr($$data{$name})){
				$errbuf .= "メールアドレスの内容に誤りがあります。半角英数字での入力をお願いします。<BR>";
				$error_hash{$name} = "メールアドレスの内容に誤りがあります。半角英数字での入力をお願いします。";
			}
		}

		#添付ファイル無効状態にもかかわらず添付ファイルを送ってきている
		if($names_hash{$name}{"type"} eq 'file' && $set_hash{"attach"} ne 'on'){
			$errbuf .= "添付ファイルの送信は禁止されております。<BR>\n";
			$error_hash{$name} = "添付ファイルの送信は禁止されております。";
			next;
		}

		#添付ファイル名が無効な場合
		if($names_hash{$name}{"type"} eq 'file' && $$data{$name} =~ m/[\r\n\\\/\:\*\?\"\<\>\|]/gi){
			$errbuf .= "添付ファイル名に利用できない文字が含まれています。「\\ \/ \* \: \* \? \" \< \> \|」は利用できません。<BR>";
			$error_hash{$name} = "添付ファイル名に利用できない文字が含まれています。「\\ \/ \* \: \* \? \" \< \> \|」は利用できません。";
			next;
		}

		#必須項目チェック
		if($names_hash{$name}{"need"} eq "need"){
			if($$data{$name} eq ""){
				$errbuf .= $names_hash{$name}{"caption"} . "は必須項目となっておりますので、必ず入力してください。<BR>";
				$error_hash{$name} = $names_hash{$name}{"caption"} . "は必須項目となっておりますので、必ず入力してください。";
			}
		}

	}
	
	return $errbuf;

}

#=========================#
# 古いテンポラリ画像データを削除
#=========================#
sub fDelOldTmp{

	my $nowtime = time;
	my $ret;
	my $dir="";
	my $dirtime="";
	#-------------------------
	
	$ret = opendir(DIR,$set_hash{"tmpfiledir"});
	if(!$ret){
		return &fDispLogError("(削除)テンポラリディレクトリをオープンできませんでした");
	}
	
	while($dirtime = $dir = readdir(DIR)){
		if($dir eq ".." || $dir eq "."){	next;	}
		$dirtime =~ s/^([0-9]+)_.*$/$1/gi;
		if($dirtime <= ($nowtime - $set_hash{"deltime"}*60*60*24)){	#ｎ日前分を削除
			unlink($set_hash{"tmpfiledir"} . $dir);
		}
	}
	
	closedir(DIR);
	
	return "";

}

#=========================#
# ログ保存
#=========================#
sub fLogging{

	my $msg = shift;
	my $i;
	my $buf="";
	my $ret;

	#-------------------------
	
	#時間、エラー内容、IP、メールアドレス（送信者メールアドレスのあるフォームの場合）
	$buf = &fDefTime(0,1) . "," . $ENV{"REMOTE_ADDR"} . "," . $msg . "\n";
	
	$ret = open(LOG,">>" . $set_hash{"logdir"} . "logs.txt");
	if(!$ret){
		return &fDispFatalError("ログファイルをオープンできませんでした。");
	}
	flock(LOG, 2);
	print LOG &_ENSET($buf);
	close(LOG);
	chmod(0666, $set_hash{"logdir"} . "logs.txt");	#ReadとWriteを付加
	
	return "";

}

#=========================#
# テンプレートを開く
#=========================#
sub fOpenTmpl{

	my $tmpl = $_[0];	#テンプレートオブジェクトを格納する変数の参照
	my $filename = $_[1];	#テンプレートファイルのパス
	#-------------------------
	
	eval {
		$$tmpl = HTML::Template->new(filename => $filename, die_on_bad_params => 0);
#		$$tmpl = HTML::Template->new(filename => $filename);
	};
	if($@){
		#テンプレートファイルのオープンに失敗
		return 1;
	}
	return 0;
}

#=========================#
# 設定情報取得
#=========================#
sub fGetSettings{

	my $i;
	my $tmp;
	#-------------------------

	#必要ファイルのチェックもここで行う。
	foreach $tmp (keys %SETTING){
		if(!(-e $SETTING{$tmp})){
			return "「" . $SETTING{$tmp} . "」ファイルが見つかりません。";
		}
	}

	#==================
	# 各種設定取得
	#==================
	$set_cnt = &fOpenSettingsData(\%set_hash);
	if($set_cnt < 0){
		return "各種設定ファイルの取得に失敗しました。ファイルが存在していない可能性があります。";
	}

	#==================
	# 項目設定取得
	#==================
	$names_cnt = &fOpenNamesData(\@names, \%names_hash);
	if($names_cnt < 0){
		return "項目設定ファイルの取得に失敗しました。ファイルが存在していない可能性があります。";
	}
	# ファイルアップロードの数を取得
	$set_hash{"tmpfilecnt"}=0;
	foreach(@names){
		if($_->{type} eq "file"){
			$set_hash{"tmpfilecnt"}++;
		}
	}

#この追加入力部分がエラーになります。
#迷惑メール対策セキュリティ要追加項目
	my $honeypot = $q->param('honeypot');
if ($honeypot) {
    # ボットによる送信と判断し、処理を中断
    return "Bot detected";
}
#迷惑メール対策セキュリティ要追加項目
my $timestamp = $q->param('timestamp');
my $current_time = time;
if ($current_time - $timestamp < 5) {  # 5秒以内に送信された場合
    # ボットによる送信と判断し、処理を中断
    return "Bot detected";
}




	#ファイル設定のチェック
	for($i=0;$i<$names_cnt;$i++){
		if($names[$i]{"type"} eq "file" && $set_hash{"attach"} ne "on"){
			return "添付ファイル設定がOffの状態で、添付ファイル用の設定が行われています。";
		}
		if($names[$i]{"type"} eq "file" && $set_hash{"deltime"} =~ m/[^0-9]/){
			return "テンポラリファイルの保存期間に数字以外が設定されています。保存期間を日数(半角数字)で指定してください。";
		}
		if($names[$i]{"type"} eq "mail" && $names[$i]{"need"} ne "need" && $set_hash{"reply"} eq "on"){
			return "自動返信を有効にしている場合は、必ずメールアドレスを必須項目としてください。";
		}
	}

	#sendmail
	if(!(-e $set_hash{"sendmailpath"})){
		return "sendmail「" . $set_hash{"sendmailpath"} . "」ファイルが見つかりません。";
	}

	#ログ用ディレクトリ
	if(!(-d $set_hash{"logdir"})){
		return &fDispFatalError("ログ用ディレクトリ「" . $set_hash{"logdir"} . "」が見つかりません。");
	}

	#テンポラリファイル保存用ディレクトリ
	if(!(-d $set_hash{"tmpfiledir"})){
		return "テンポラリファイル用ディレクトリ「" . $set_hash{"tmpfiledir"} . "」が見つかりません。";
	}
	
	if($set_hash{"url_complete"} eq ""){
		return "完了画面のURLが設定されていません。";
	}

	if($set_hash{"to"} eq ""){
		return "受信用アドレス「to」が設定されていません。";
	}

	if($set_hash{"from"} eq ""){
		return "返信用差出人アドレス「from」が設定されていません。";
	}

	if(!($set_hash{"tmpfiledir"} =~ m/\/$/)){
		$set_hash{"tmpfiledir"} .= '/';
	}
	
	if(!($set_hash{"logdir"} =~ m/\/$/)){
		$set_hash{"logdir"} .= '/';
	}
	
	return "";

}

#=========================#
# 名前設定情報取得
#=========================#
sub fOpenNamesData{

	my $list = shift;
	my $hash = shift;
	my $buf="";
	my $i=0;
	my $ret;
	#-------------------------
	$ret = open(DATA, "<:encoding(shiftjis)", $SETTING{"data_names"});
	if(!$ret){
		return -1;
	}

	foreach $buf (<DATA>){
		chomp($buf);
		my($name, $caption, $type, $need) = split(/,/,$buf);
		if($name =~ m/^\#/){	next;	}	#「#」が付いている行は飛ばす
		
		$$list[$i]{"name"} = $name;
		$$list[$i]{"caption"} = $caption;
		$$list[$i]{"type"} = $type;
		$$list[$i]{"need"} = $need;
		
		#名前でアクセスできるように
		$$hash{$name}{"caption"} = $caption;
		$$hash{$name}{"type"} = $type;
		$$hash{$name}{"need"} = $need;
		$i++;
	}
	close(DATA);
	
	return $i;

}

#=========================#
# 各種設定情報取得
#=========================#
sub fOpenSettingsData{

	my $hash = shift;
	my $buf="";
	my $i=0;
	my $ret;
	#-------------------------
	$ret = open(DATA, "<:encoding(shiftjis)", $SETTING{"data_settings"});

	if(!$ret){
		return -1;
	}
	
	foreach $buf (<DATA>){
		$buf =~ s/[\r\n]//gi;
		my($name, $data) = split(/,/,$buf);
		if($name =~ m/^\#/){	next;	}	#「#」が付いている行は飛ばす
		
		#名前でアクセスできるように
		$$hash{$name} = $data;
		$i++;
	}
	close(DATA);
	
	return $i;

}

#=========================#
# パスからファイル名だけを取得
#=========================#
sub fGetFilename{
	
	my $fname = shift;
	my $i;
	#-------------------------
	
	if($fname =~ m/[\/\\]/){
		for($i=0;$i<length($fname);$i++){
			if(substr($fname, ($i+1)*-1, 1) eq '/' || substr($fname, ($i+1)*-1, 1) eq "\\"){
				last;
			}
		}
		$fname = substr($fname, ($i)*-1, length($fname)-($i));
	}
	
	return $fname;

}

#=========================#
# 通常エラー
#=========================#
sub fDispError{

	my $msg = $_[0];
	my $ret;
	my $tmpl;
	#-------------------------

	if($msg eq "END"){	return;	}	#すでに処理されている。

	#テンプレート差し込み
	$ret = &fOpenTmpl(\$tmpl, $SETTING{"tmpl_error"});
	if($ret){	return &fDispLogError("エラーテンプレートの読み込みに失敗しました");	}

	eval{
		$tmpl->param(&_ENSET("error") => &_ENSET($msg));
	};
	
	if($@){	return &fDispLogError("エラー画面の作成に失敗しました");	}

	&fPrintHeader(0,"");
	print $tmpl->output();

	undef $tmpl;
	
	return "END";
}

#=========================#
# エラー表示(ログ取得)
#=========================#
sub fDispLogError{

	my $msg = $_[0];
	#-------------------------

	if($msg eq "END"){	return;	}	#すでに処理されている。

	&fPrintHeader(0,"");
	print &_ENSET("<html><head><title>エラー</title></head><body>エラー<BR>" . $msg . '<BR><input type="button" value="戻る" onClick="history.back();"></body></html>');

	#ログ
	&fLogging($msg);

	return "END";

}

#=========================#
# エラー表示(致命的エラー)
#=========================#
sub fDispFatalError{

	my $msg = $_[0];
	#-------------------------

	if($msg eq "END"){	return;	}	#すでに処理されている。

	&fPrintHeader(0,"");
	print &_ENSET("<html><head><title>エラー</title></head><body>エラー<BR>" . $msg . '<BR><input type="button" value="戻る" onClick="history.back();"></body></html>');

	return "END";

}

#=========================#
# ヘッダ出力
#=========================#
sub fPrintHeader{

	my $param = $_[0];
	my $url = $_[1];
	#-------------------------
	
	if($param == 1){
		print 'Location: ' . $url . "\n\n";
	}else{
		if($set_hash{"encmode"} eq "utf8"){
			print "Content-Type: text/html;charset=UTF-8\n\n";
		}else{
			print "Content-Type: text/html;charset=Shift_JIS\n\n";
		}
	}

}

#=========================#
# Base64エンコード(base64.pl)
#=========================#
sub fEncodeBase64{
	my $tempbuf = shift;
	#-------------------------
	return &base64::b64encode($tempbuf);
}

#-------------------------------------------------------------------------------------------
# 汎用関数
#-------------------------------------------------------------------------------------------

#=========================#
# HTMLを無害化(サニタイジング)
#=========================#
sub fHTMLSanitizing{

	my $buf = $_[0];
	#-------------------------
	
	$buf =~ s/&/&amp;/gi;
	$buf =~ s/"/&quot;/gi;
	$buf =~ s/'/&#39;/gi;
	$buf =~ s/</&lt;/gi;
	$buf =~ s/>/&gt;/gi;

	return $buf;

}

#=========================#
# Hiddenタグ作成
#=========================#
sub fCreateHidden{

	my $name = $_[0];
	my $value = $_[1];
	my $buf;
	#-------------------------

	$buf = '<input type="hidden" name="' . $name . '" value="' . $value . '">' . "\n";
	
	return $buf;

}

#=========================#
# 改行をBRに
#=========================#
sub fCRLFtoBR{

	my $buf = $_[0];
	#-------------------------
	
	$buf =~ s/\r\n/\n/gi;
	$buf =~ s/\r//gi;
	$buf =~ s/\n/<BR>/gi;
	
	return $buf;

}

#=========================#
# 全角英数記号を半角に（メールアドレス用）
#=========================#
sub fHankakuToZenkaku{

	my $buf = $_[0];
	#-------------------------

	$buf =~ tr/０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ＠，．、。＿/0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\@\,\.\,\._/;
	
	#ハイフンにはいろんな種類がある
	$buf =~ s/[\x{02D7}\x{2010}-\x{2012}\x{2212}\x{FE63}\x{FF0D}\x{2015}\x{2500}\x{2501}\x{30FC}]/-/g;

	return $buf;

}

#=========================#
# 時間の取得
#=========================#
sub fDefTime{

	my $difference = $_[0]; #時間差
	my $type = $_[1];       #1: "YYYY/MM/DD HH:MM:SS" 2: YYYYMMDDHHMMSS 3:Year 4:Mon 5: mday 6: hour 7: min 8: sec 9: wday)
	$type = $type eq "" ? 99 : $type;

	my @day = ();
	my @j_day = ();
	my @m = ();
	my @j_m = ();
	#-------------------------

	$day[0] = 'Sun';	$day[1] = 'Mon';	$day[2] = 'Tue';	$day[3] = 'Wed';
	$day[4] = 'Thu';	$day[5] = 'Fri';	$day[6] = 'Sat';

	$j_day[0] = '日';	$j_day[1] = '月';	$j_day[2] = '火';	$j_day[3] = '水';
	$j_day[4] = '木';	$j_day[5] = '金';	$j_day[6] = '土';

	$m[0]="Jan"; $m[1]="Feb"; $m[2]="Mar"; $m[3]="Apr"; $m[4]="May"; $m[5]="Jun";
	$m[6]="Jul"; $m[7]="Aug"; $m[8]="Sep"; $m[9]="Oct"; $m[10]="Nov"; $m[11]="Dec";

	$j_m[0]="1"; $j_m[1]="2"; $j_m[2]="3"; $j_m[3]="4"; $j_m[4]="5"; $j_m[5]="6";
	$j_m[6]="7"; $j_m[7]="8"; $j_m[8]="9"; $j_m[9]="10"; $j_m[10]="11"; $j_m[11]="12";

	my ($sec, $min, $hour, $mday, $mon, $year, $wday) = localtime(time+$difference);
	$mon++;
	$mon = $mon < 10 ? "0" . $mon : $mon;
	$mday = $mday < 10 ? "0" . $mday : $mday;
	$hour = $hour < 10 ? "0" . $hour : $hour;
	$min = $min < 10 ? "0" . $min : $min;
	$sec = $sec < 10 ? "0" . $sec : $sec;
	$year+=1900;

	if($type == 1){	 return "$year/$mon/$mday $hour:$min:$sec";	}
	elsif($type == 2){	return "$year$mon$mday$hour$min$sec";	}
	elsif($type == 3){	return $year;	}
	elsif($type == 4){	return $mon;	}
	elsif($type == 5){	return $mday;	}
	elsif($type == 6){	return $hour;	}
	elsif($type == 7){	return $min;	}
	elsif($type == 8){	return $sec;	}
	elsif($type == 9){	return $wday;	}
	elsif($type == 10){	return "$day[$wday]\, $mday\-$m[($mon-1)]\-$year $hour:$min:$sec";	}
	elsif($type == 11){	return "$year\-$j_m[($mon-1)]\-$mday($j_day[$wday]) $hour:$min:$sec";	}
	else{	return "$year/$mon/$mday $hour:$min:$sec";	}

}

#=========================#
# メールアドレスの有効性チェック
#=========================#
sub fCheckMailAddr{
	my $mailaddr = shift;
	#-------------------------
	if($mailaddr ne "" && !($mailaddr =~ /^[a-zA-Z0-9\!\#\$\%\&\'\*\+\-\/\=\?\^\_\`\{\|\}\~\.]+@[a-zA-Z0-9\!\#\$\%\&\'\*\+\-\/\=\?\^\_\`\{\|\}\~\.]+\.[a-zA-Z0-9]+$/) || $mailaddr =~ /\.\./ ){
		return 1;
	}
	return 0;
}

sub _ENSET{

	my $buf = shift;
	my $encmode = $set_hash{"encmode"};

	if($encmode eq "shift-jis" || $encmode eq "utf8"){
		return OCChar->EncodeSet($encmode, $buf);
	}else{
		return OCChar->EncodeSet("shift-jis", $buf);
	}

}

sub _DCSET{

	my $buf = shift;
	my $encmode = $set_hash{"encmode"};

	if($encmode eq "shift-jis" || $encmode eq "utf8"){
		return OCChar->DecodeSet($encmode, $buf);
	}else{
		return OCChar->DecodeSet("shift-jis", $buf);
	}

}

1;

#END#