export default function FeedbackTab({ feedback }) {
  return (
    <div className="space-y-4">
      <h3 className="font-medium text-gray-900">User Feedback</h3>
      {feedback.length === 0 ? (
        <p className="text-gray-500 text-sm">No feedback submissions</p>
      ) : (
        <div className="divide-y">
          {feedback.map(item => (
            <div key={item.id} className="py-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      item.type === 'bug' ? 'bg-red-100 text-red-700' :
                      item.type === 'feature' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {item.type || 'suggestion'}
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      item.status === 'resolved' ? 'bg-amber-100 text-amber-700' :
                      item.status === 'in_progress' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {item.status || 'pending'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mt-1">
                    From: {item.name || 'Anonymous'} {item.email && `<${item.email}>`}
                  </div>
                  <p className="text-gray-800 mt-2 whitespace-pre-wrap">{item.message}</p>
                  <div className="text-xs text-gray-400 mt-1">
                    {item.created_at && new Date(item.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
