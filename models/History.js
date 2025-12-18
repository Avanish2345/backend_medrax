const mongoose = require('mongoose');

const HistorySchema = new mongoose.Schema({
  imageBase64: String,
  report: String,
  qa: [{
    question: String,
    answer: String,
    createdAt: { type: Date, default: Date.now }
  }],
  createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('History', HistorySchema);
