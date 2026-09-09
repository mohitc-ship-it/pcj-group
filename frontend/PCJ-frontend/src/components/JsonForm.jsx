export default function JsonForm({ data, onChange }) {
    function update(key, value) {
      onChange({ ...data, [key]: value });
    }
  
    return (
      <div className="form">
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="field">
            <label>{key}</label>
  
            {typeof value === "string" && (
              <input
                value={value}
                onChange={e => update(key, e.target.value)}
              />
            )}
  
            {typeof value === "number" && (
              <input
                type="number"
                value={value}
                onChange={e => update(key, Number(e.target.value))}
              />
            )}
          </div>
        ))}
      </div>
    );
  }
  