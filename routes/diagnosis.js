const express = require('express');
const router = express.Router();
const axios = require('axios');
const GEMINI_API_KEY = 'AIzaSyDVNtWtbJAT0TM19ATKj5g2U4wfLFuXm7I';

router.post('/report', async (req, res) => {
  try {
    if (!req.files || !req.files.file) {
      return res.status(400).json({ error: 'No image uploaded' });
    }
    const image = req.files.file.data;
    const imageBase64 = image.toString('base64');
    const prompt = "You are a meticulous radiologist. Give a detailed, structured report (findings, impression, recommendations) on this chest X-ray.";
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key=${GEMINI_API_KEY}`;
    const payload = {
      contents: [{
        parts: [
          { text: prompt },
          { inline_data: { mime_type: "image/jpeg", data: imageBase64 }}
        ]
      }]
    };
    const response = await axios.post(url, payload);
    const report = response?.data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No report generated';
    res.json({ report });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error generating report', details: err.message });
  }
});

router.post('/followup', async (req, res) => {
  try {
    const { report, question } = req.body;
    const prompt = `Given this radiology report:\n${report}\n\nAnswer this follow-up question: ${question}`;
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=${GEMINI_API_KEY}`;
    const payload = {
      contents: [{
        parts: [{ text: prompt }]
      }]
    };
    const response = await axios.post(url, payload);
    const answer = response?.data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No answer';
    res.json({ answer });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error answering question', details: err.message });
  }
});

module.exports = router;
