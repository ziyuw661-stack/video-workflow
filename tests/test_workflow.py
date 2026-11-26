import datetime as dt
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from core import discovery
from core.youtube_publish import future_time, channel
from workflow import Account, CHECKS, artifacts, locked, publish, read, review, tick, validate_evidence, write


class WorkflowTests(TestCase):
    def setUp(self):
        folder=TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.config=self.root/"profile.json"
        write(self.config, {"account_id":"alpha","timezone":"UTC","workspace":str(self.root/"desktop"),
            "state_root":str(self.root/"local"),"production_accepted":True,
            "schedule":{"collect":"09:00","generate":"09:05"},
            "publication":{"manual_hosts":["youtu.be"]}})
        self.account=Account(self.config)

    def test_single_writer(self):
        with locked(self.account), self.assertRaisesRegex(ValueError,"already running"):
            with locked(self.account):
                pass

    def test_schedule_depends_on_collect_and_never_reruns(self):
        moment=dt.datetime(2026,11,26,9,8,tzinfo=dt.timezone.utc)
        with mock.patch("workflow.collect",side_effect=ValueError("network down")), mock.patch("workflow.scheduled_generate") as render:
            result=tick(self.account,moment)
            self.assertEqual(result["stages"]["collect"]["state"],"failed")
            self.assertEqual(tick(self.account,moment)["stages"],{})
            render.assert_not_called()

    def test_successful_tick_is_idempotent(self):
        moment=dt.datetime(2026,11,26,9,8,tzinfo=dt.timezone.utc)
        with mock.patch("workflow.collect",return_value={}), mock.patch("workflow.scheduled_generate",return_value={"status":"pending_review"}) as render:
            self.assertEqual(list(tick(self.account,moment)["stages"]),["collect","generate"])
            self.assertEqual(tick(self.account,moment)["stages"],{})
            render.assert_called_once()

    def test_scheduler_requires_acceptance(self):
        self.account.p["production_accepted"]=False
        with self.assertRaisesRegex(ValueError,"accepted"):
            tick(self.account)

    def test_cross_account_path_and_credential_guards(self):
        p=read(self.config)
        p["state_root"]=p["workspace"]
        write(self.config,p)
        with self.assertRaisesRegex(ValueError,"separate"):
            Account(self.config)
        p["state_root"]=str(self.root/"local")
        p["api_key"]="secret"
        write(self.config,p)
        with self.assertRaisesRegex(ValueError,"credentials"):
            Account(self.config)

    def seed(self, sample=False):
        output=self.account.out("job")
        output.mkdir()
        for f in ("final.mp4","final.srt","cover.png","publish.json","script.json","timeline.json","evidence.json"):
            (output/f).write_bytes(b"test")
        write(output/"qc.json",{"technical_checks":"passed"})
        write(output/"job.json",{"sample":sample})
        checklist=self.root/"qa.json"
        write(checklist,{"decision":"approve","reviewer":"teammate","score":90,**dict.fromkeys(CHECKS,True)})
        return output,checklist

    def test_sample_and_mutated_file_are_blocked(self):
        output,checklist=self.seed(sample=True)
        review(self.account,"job",checklist)
        with self.assertRaisesRegex(ValueError,"non-sample"):
            publish(self.account,"job","https://youtu.be/abc")
        write(output/"job.json",{"sample":False})
        with self.assertRaisesRegex(ValueError,"unchanged"):
            publish(self.account,"job","https://youtu.be/abc")

    def test_manual_approval_and_idempotent_publication_record(self):
        _,checklist=self.seed()
        self.assertRaises(FileNotFoundError,publish,self.account,"job","https://youtu.be/abc")
        review(self.account,"job",checklist)
        with self.assertRaisesRegex(ValueError,"platform host"):
            publish(self.account,"job","https://youtu.be.fake.com/abc")
        result=publish(self.account,"job","https://youtu.be/abc")
        self.assertEqual(result,publish(self.account,"job","https://youtu.be/abc"))
        with self.assertRaisesRegex(ValueError,"already exists"):
            publish(self.account,"job","https://youtu.be/xyz")

    def test_topic_dedup_missing_metrics_and_export(self):
        a=self.account
        row={"platform":"youtube","video_id":"id","title":"=DANGEROUS","url":"https://youtu.be/example"}
        with closing(a.db()) as db:
            discovery.ingest(db,[row,row])
            self.assertEqual(db.execute("select count(*) from topics").fetchone()[0],1)
            discovery.assess(db,[{"platform":"youtube","video_id":"id","source_allowed":True,
                                  "match":90,"originality":80,"feasible":80}])
            topic=discovery.get_topic(db)
            self.assertEqual(topic["video_id"],"id")
            self.assertAlmostEqual(topic["confidence"],.5)
            discovery.export(db,a.home/"exports",a.today())
        from openpyxl import load_workbook
        wb=load_workbook(a.home/"exports"/"选题总库.xlsx")
        self.addCleanup(wb.close)
        self.assertEqual(wb.active["C2"].data_type,"s")
        self.assertIsNone(wb.active["H2"].value)

    def test_youtube_channel_and_future_time(self):
        yt=mock.Mock()
        yt.channels().list().execute.return_value={"items":[{"id":"different"}]}
        with self.assertRaisesRegex(ValueError,"channel"):
            channel(yt,"correct")
        now=dt.datetime(2026,11,26,tzinfo=dt.timezone.utc)
        self.assertEqual(future_time("2026-11-27T01:00:00+08:00",now),"2026-11-26T17:00:00Z")
        for value in ("2026-11-26T01:00:00","2026-11-25T01:00:00Z"):
            with self.assertRaises(ValueError):
                future_time(value,now)

    def test_evidence_requires_real_urls_and_confirmation(self):
        entry={"url":"https://example.org/source","id":"a","claim":"checked","verified":True}
        self.assertEqual(validate_evidence([entry]),{"a"})
        for bad in ([entry,entry],[{**entry,"verified":False}],[{**entry,"url":"file:///source"}]):
            with self.assertRaises(ValueError):
                validate_evidence(bad)
