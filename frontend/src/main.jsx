import React,{useState,useRef} from "react";
import {createRoot} from "react-dom/client";
import {Upload,Play,Languages,Loader2,CheckCircle2,Download} from "lucide-react";
import "./style.css";

const API=import.meta.env.VITE_API_URL || "http://localhost:8000";
function App(){
 const [file,setFile]=useState(null),[loading,setLoading]=useState(false),[segments,setSegments]=useState([]),[job,setJob]=useState(null),[error,setError]=useState("");
 const [drag,setDrag]=useState(false), audio=useRef(null), [current,setCurrent]=useState(0);
 const choose=e=>{const f=e.target.files?.[0];if(f)setFile(f);setError("")};
 async function start(){
  if(!file)return;
  setLoading(true);setError("");setSegments([]);setJob(null);
  try{let fd=new FormData();fd.append("file",file);let r=await fetch(API+"/api/translate",{method:"POST",body:fd});let d=await r.json();if(!r.ok)throw Error(d.detail||"Gagal memproses");setSegments(d.segments);setJob(d);}
  catch(e){setError(e.message)} finally{setLoading(false)}
 }
 const setAt=(i,key,val)=>setSegments(s=>s.map((x,n)=>n===i?{...x,[key]:val}:x));
 function seek(t){if(audio.current){audio.current.currentTime=t;audio.current.play()}}
 return <div className="app">
  <header><div className="brand"><div className="logo">JP</div><div><b>JP → ID</b><span> Subtitle Translator</span></div></div><div className="pill"><Languages size={15}/> Groq AI</div></header>
  <main>
   <section className="hero"><div className="eyebrow">JAPANESE AUDIO / VIDEO</div><h1>Ubah audio Jepang<br/><em>menjadi subtitle Indonesia.</em></h1><p>Transkripsi otomatis, terjemahan natural, timestamp tetap sinkron, dan ekspor SRT/VTT.</p></section>
   <section className={"drop "+(drag?"drag":"")} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);let f=e.dataTransfer.files[0];if(f){setFile(f);setError("")}}}>
    <input id="file" type="file" accept="audio/*,video/*" onChange={choose}/>
    <label htmlFor="file"><div className="uploadIcon"><Upload/></div><h3>{file?file.name:"Pilih audio atau video"}</h3><p>{file?`${(file.size/1024/1024).toFixed(1)} MB — siap diproses`:"MP3, WAV, M4A, MP4, MOV, WEBM, MKV, AVI"}</p><button>Browse file</button></label>
   </section>
   {error&&<div className="error">{error}</div>}
   <button className="primary" disabled={!file||loading} onClick={start}>{loading?<><Loader2 className="spin"/> Memproses audio & menerjemahkan…</>:<><Play size={18}/> Mulai Terjemahkan</>}</button>
   {loading&&<div className="progress"><div></div><small>Groq Whisper → terjemahan Jepang ke Indonesia. Waktu bergantung durasi audio.</small></div>}
   {segments.length>0&&<section className="result">
    <div className="resultHead"><div><div className="eyebrow">HASIL TERJEMAHAN</div><h2>{segments.length} subtitle segments</h2></div>
      <div className="actions"><a href={API+job.srt_url} download><Download size={16}/> SRT</a><a href={API+job.vtt_url} download><Download size={16}/> VTT</a></div>
    </div>
    <audio ref={audio} src={file?URL.createObjectURL(file):""} controls onTimeUpdate={e=>setCurrent(e.target.currentTime)}/>
    <div className="table">
     <div className="thead"><span>TIME</span><span>JEPANG</span><span>INDONESIA</span></div>
     {segments.map((s,i)=><div className={"row "+(current>=s.start&&current<=s.end?"active":"")} key={i} onClick={()=>seek(s.start)}>
       <span className="time">{fmt(s.start)}<br/>→ {fmt(s.end)}</span><textarea value={s.ja} onChange={e=>setAt(i,"ja",e.target.value)}/><textarea value={s.id_text} onChange={e=>setAt(i,"id_text",e.target.value)}/>
     </div>)}
    </div>
   </section>}
  </main>
  <footer><CheckCircle2 size={15}/> API key diproses di backend — tidak dikirim ke browser</footer>
 </div>
}
function fmt(x){let m=Math.floor(x/60),s=(x%60).toFixed(1).padStart(4,"0");return `${String(m).padStart(2,"0")}:${s}`}
createRoot(document.getElementById("root")).render(<App/>);
