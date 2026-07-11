import React, { useEffect, useState } from "react";
import { listJobs } from "./api.js";

export default function JobBoard({ onApply }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-center muted">Loading openings…</div>;
  if (error) return <div className="page-center error">{error}</div>;

  return (
    <div className="job-board">
      <div className="jb-header">
        <h2>Open positions</h2>
        <p className="muted">Submit your resume and our AI will interview you immediately.</p>
      </div>
      {jobs.length === 0 ? (
        <div className="empty-state muted">No openings right now. Check back soon.</div>
      ) : (
        <div className="job-list">
          {jobs.map((job) => (
            <div key={job.job_id} className="job-card">
              <div className="job-card-body">
                <h3>{job.title}</h3>
                <div className="job-meta">
                  <span className="tag">{job.employment_type}</span>
                  <span className="tag">{job.location}</span>
                  <span className="muted">{job.application_count} applicants</span>
                </div>
              </div>
              <button onClick={() => onApply(job.job_id)}>Apply now</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
