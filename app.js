/*const express = require('express');
const cors = require('cors');
const fileUpload = require('express-fileupload');
const diagnosisRoutes = require('./routes/diagnosis');

const app = express();

app.use(cors());
app.use(express.json());
app.use(fileUpload({ limits: { fileSize: 50 * 1024 * 1024 } }));

app.use('/api/diagnosis', diagnosisRoutes);
app.get("/", (req, res) => {
  res.json({ message: "MedRAX Node backend is running" });
});


module.exports = app;*/
require('dotenv').config();

const express = require('express');
const cors = require('cors');
const fileUpload = require('express-fileupload');
const mongoose = require('mongoose');
const diagnosisRoutes = require('./routes/diagnosis');

const app = express();

app.use(cors());
app.use(express.json());
app.use(fileUpload());

mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("MongoDB connected"))
  .catch(err => console.error("MongoDB error:", err));

app.use('/api/diagnosis', diagnosisRoutes);

module.exports = app;




